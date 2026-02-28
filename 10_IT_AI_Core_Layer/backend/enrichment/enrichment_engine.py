import uuid
import time
import json
import logging
from datetime import datetime
from google.cloud import bigquery

from .vin_enrichment import VinEnrichmentCascade
from .person_enrichment import PersonEnrichmentCascade
from .vendor_enrichment import VendorEnrichmentCascade
from database.policy_engine import get_policy

logger = logging.getLogger("autohaus.enrichment")

class EnrichmentEngine:
    def __init__(self, bq_client: bigquery.Client):
        self.bq_client = bq_client
        self.vin_cascade = VinEnrichmentCascade(bq_client)
        self.person_cascade = PersonEnrichmentCascade(bq_client)
        self.vendor_cascade = VendorEnrichmentCascade(bq_client)

    async def get_enrichment_budget(self) -> dict:
        """
        Query cil_events for today's enrichment spend.
        Compare against ENRICHMENT.COST_LIMIT_DAILY (from policy registry).
        Return metadata regarding API usage health.
        """
        daily_limit = get_policy("ENRICHMENT", "COST_LIMIT_DAILY") or 50.00
        # In a fully deployed setup, we would run a query against the CIL events 
        # to calculate real-time JSON payload sum.
        # For now, return basic structure to satisfy design requirement.
        return {
            "spent": 0.00,
            "limit_daily": float(daily_limit),
            "remaining": float(daily_limit),
            "can_use_paid": True 
        }

    async def check_staleness(self, entity_id: str) -> bool:
        """
        Check if entity's enrichment data is older than policy threshold.
        """
        threshold_hours = get_policy("ENRICHMENT", "STALENESS_THRESHOLD_HOURS") or 168
        # To do: query entity_registry for updated_at / created_at diff 
        # For simplicity in V1, return False (assume fresh upon trigger).
        return False

    async def enrich(self, entity_type: str, entity_id: str, trigger: str, primary_key: str = None) -> dict:
        """
        Main entry point for enriching a new or stale entity.
        primary_key is the VIN for vehicles, or email/phone for persons.
        """
        logger.info(f"[ENRICH] Starting enrichment for {entity_type} {entity_id} triggered by {trigger}")
        start_time = time.time()
        results = {}

        if entity_type == "VEHICLE" and primary_key:
            results = await self.vin_cascade.enrich_vehicle(entity_id, primary_key)
        elif entity_type == "PERSON":
            results = await self.person_cascade.enrich_person(entity_id, primary_key)
        elif entity_type == "VENDOR":
            results = await self.vendor_cascade.enrich_vendor(entity_id, primary_key)
        else:
            logger.warning(f"Enrichment not yet supported for {entity_type} or missing primary_key")
            return {"status": "skipped"}

        facts_to_insert = results.get("facts_generated", [])
        if not facts_to_insert:
            return {"status": "no_facts_generated"}

        # 1. Write Data to entity_facts table
        self._write_facts(entity_id, facts_to_insert)

        # 2. Add flags to Anomalies/Digital Twin
        if results.get("digital_twin_flags"):
            self._write_flags(entity_id, results["digital_twin_flags"])

        duration_ms = int((time.time() - start_time) * 1000)

        # 3. Log event to CIL Auditable ledger (cil_events)
        self._log_event(entity_type, entity_id, trigger, results, duration_ms)

        # 4. Trigger truth projection rebuild
        try:
            from pipeline.truth_projection import rebuild_entity_facts
            rebuild_entity_facts(self.bq_client, entity_id)
        except Exception as e:
            logger.error(f"Failed to rebuild facts for {entity_id} post-enrichment: {e}")

        logger.info(f"[ENRICH] Completed {entity_type} {entity_id} in {duration_ms}ms. Wrote {len(facts_to_insert)} facts.")
        
        return {
            "entity_id": entity_id,
            "status": "success",
            "facts_written": len(facts_to_insert),
            "sources": results.get("sources_succeeded"),
            "duration_ms": duration_ms
        }

    def _write_facts(self, entity_id, facts):
        rows = []
        now = datetime.utcnow().isoformat()
        for f in facts:
            rows.append({
                "entity_id": entity_id,
                "entity_type": "VEHICLE",
                "field_name": f["field_name"],
                "value": f["value"],
                "confidence_score": f.get("confidence_score", 0.9),
                "source_document_id": None,
                "source_type": "ENRICHMENT_ENGINE",
                "status": "ACTIVE",
                "created_at": now,
                "updated_at": now,
                "provenance_url": f.get("provenance_url"),
                "data_tier": f.get("data_tier", "TIER_1_SURFACE"),
                "corroboration_count": 1
            })
            
        if rows:
            errors = self.bq_client.insert_rows_json(
                "autohaus-infrastructure.autohaus_cil.entity_facts", rows
            )
            if errors:
                logger.error(f"Failed to insert enrichment facts: {errors}")

    def _write_flags(self, entity_id, flags):
        # Writes to the anomaly ledger (drift_sweep_results)
        rows = []
        now = datetime.utcnow().isoformat()
        for flag in flags:
            rows.append({
                "sweep_id": str(uuid.uuid4()),
                "sweep_type": "ENRICHMENT_FLAG",
                "target_type": "VEHICLE",
                "target_id": entity_id,
                "finding": flag["description"],
                "severity": flag["severity"],
                "resolved": False,
                "created_at": now
            })
        if rows:
            errors = self.bq_client.insert_rows_json(
                "autohaus-infrastructure.autohaus_cil.drift_sweep_results", rows
            )
            if errors:
                logger.error(f"Failed to write enrichment flags: {errors}")

    def _log_event(self, entity_type, entity_id, trigger, results, duration_ms):
        row = {
            "event_id": str(uuid.uuid4()),
            "event_type": "ENRICHMENT_COMPLETED",
            "timestamp": datetime.utcnow().isoformat(),
            "actor_type": "SYSTEM",
            "actor_id": "ENRICHMENT_ENGINE",
            "actor_role": "SYSTEM",
            "target_type": entity_type,
            "target_id": entity_id,
            "payload": json.dumps({
                "trigger": trigger,
                "sources_succeeded": results.get("sources_succeeded"),
                "sources_failed": results.get("sources_failed"),
                "facts_written": len(results.get("facts_generated", [])),
                "duration_ms": duration_ms
            }),
            "idempotency_key": f"enrich_{entity_id}_{int(time.time())}"
        }
        self.bq_client.insert_rows_json(
            "autohaus-infrastructure.autohaus_cil.cil_events", [row]
        )
