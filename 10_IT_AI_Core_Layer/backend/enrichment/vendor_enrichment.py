import asyncio
import logging
from typing import Dict, Any

from database.policy_engine import get_policy
# from .connectors.business_registry import BusinessRegistryConnector

logger = logging.getLogger("autohaus.enrichment.vendor")

class VendorEnrichmentCascade:
    def __init__(self, bq_client):
        self.bq_client = bq_client
        # self.business_registry = BusinessRegistryConnector(bq_client)

    async def enrich_vendor(self, entity_id: str, primary_key: str) -> Dict[str, Any]:
        """Runs the enrichment cascade for a Vendor."""
        results = {
            "entity_id": entity_id,
            "primary_key": primary_key,
            "sources_queried": ["ALIAS_NORMALIZATION", "CIL_HISTORY"],
            "sources_succeeded": [],
            "sources_failed": [],
            "facts_generated": [],
            "digital_twin_flags": []
        }
        
        # Check Allowed Sources
        auto_sources = get_policy("ENRICHMENT", "VENDOR.AUTO_SOURCES") or ["ALIAS_NORMALIZATION", "CIL_HISTORY"]
        
        if "CIL_HISTORY" in auto_sources:
            try:
                # Query CIL Events for this vendor to calculate transaction count, spend, etc.
                query = """
                    SELECT event_type, COUNT(*) as event_count
                    FROM `autohaus-infrastructure.autohaus_cil.cil_events`
                    WHERE target_id = @entity_id OR actor_id = @entity_id
                    GROUP BY event_type
                """
                from google.cloud import bigquery
                job_config = bigquery.QueryJobConfig(
                    query_parameters=[bigquery.ScalarQueryParameter("entity_id", "STRING", entity_id)]
                )
                event_rows = list(self.bq_client.query(query, job_config=job_config).result())
                
                total_events = sum(r.event_count for r in event_rows)
                
                results["sources_succeeded"].append("CIL_HISTORY")
                results["facts_generated"].append({
                    "field_name": "historical_event_count",
                    "value": str(total_events),
                    "fact_category": "VENDOR_SCORECARD",
                    "authority_level": "AUTO_ENRICHED",
                    "confidence_score": 1.0,
                    "provenance_url": "internal://cil_events",
                    "data_tier": "TIER_2_OPERATIONAL"
                })
            except Exception as e:
                logger.error(f"[ENRICH] CIL_HISTORY scan failed for vendor {entity_id}: {e}")
                results["sources_failed"].append("CIL_HISTORY")

        # Step 3 - Business Registry Lookup (Only if in policy)
        on_demand_sources = get_policy("ENRICHMENT", "VENDOR.ON_DEMAND_SOURCES") or []
        if "BUSINESS_REGISTRY" in on_demand_sources:
            # We would invoke the SOS business registry provider here
            pass

        return results
