import json
import logging
from typing import Dict, Any, List, Optional
from database.bigquery_client import BigQueryClient

logger = logging.getLogger("autohaus.intelligence.checkpoint")

class IntelligenceCheckpoint:
    def __init__(self, bq_client: Optional[BigQueryClient] = None):
        self.bq = bq_client or BigQueryClient()
        self.ontology = self._load_ontology()

    def _load_ontology(self) -> Dict[str, Any]:
        try:
            with open("registry/business_ontology.json", "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[CHECKPOINT] Failed to load ontology: {e}")
            return {}

    async def check_fact(self, target_type: str, target_id: str, fact: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for checking a proposed fact.
        Returns check result with conflicts and questions.
        """
        result = {"conflicts": [], "clear": True, "questions": []}
        
        # 1. Contradiction & Ambiguity Check
        if target_type == "VENDOR":
            await self._check_vendor(target_id, fact, result)
        elif target_type == "VEHICLE":
            await self._check_vehicle(target_id, fact, result)
        
        # 2. Missing Context Check
        self._check_missing_context(target_type, target_id, fact, result)

        if result["conflicts"] or result["questions"]:
            result["clear"] = False
            
        return result

    async def _check_vendor(self, target_id: str, fact: Dict[str, Any], result: Dict[str, Any]):
        # Strategy Conflict: Progressive vs Auto-Owners
        if "progressive" in target_id.lower() or "progressive" in fact.get("name", "").lower():
            # Check if ontology specifies single carrier strategy
            # For now, we hardcode the check since ontology is still evolving
            result["conflicts"].append("STRATEGY_CONFLICT")
            result["questions"].append(
                "Documents show Progressive Southeastern Insurance as an active carrier. "
                "This conflicts with the single-carrier Auto-Owners strategy in the business ontology. "
                "Is Progressive a current carrier, a former carrier, or coverage for a specific use case?"
            )

        # Registry Contradiction Check
        query = f"""
            SELECT canonical_name, authority_level 
            FROM `autohaus-infrastructure.autohaus_cil.entity_registry`
            WHERE entity_id = @target_id OR canonical_name = @name
            LIMIT 1
        """
        from google.cloud import bigquery as bq
        job_config = bq.QueryJobConfig(
            query_parameters=[
                bq.ScalarQueryParameter("target_id", "STRING", target_id),
                bq.ScalarQueryParameter("name", "STRING", fact.get("name", "")),
            ]
        )
        try:
            rows = list(self.bq.client.query(query, job_config=job_config).result())
            if rows:
                existing = rows[0]
                # If we're proposing a name change to a VERIFIED entity
                if existing.authority_level == "VERIFIED" and fact.get("name") and existing.canonical_name != fact.get("name"):
                    result["conflicts"].append("REGISTRY_CONTRADICTION")
                    result["questions"].append(f"Proposed name '{fact.get('name')}' differs from verified registry name '{existing.canonical_name}'.")
        except Exception as e:
            logger.warning(f"[CHECKPOINT] Registry check failed: {e}")

    async def _check_vehicle(self, target_id: str, fact: Dict[str, Any], result: Dict[str, Any]):
        # Check for multiple owners/titles (Ambiguity)
        pass

    def _check_missing_context(self, target_type: str, target_id: str, fact: Dict[str, Any], result: Dict[str, Any]):
        # Logic for expected but absent data
        if target_type == "VENDOR" and fact.get("relationship_type") == "ACTIVE_VENDOR":
            # Missing payment method or tax ID?
            pass
        
        if target_type == "VEHICLE" and "transport" in str(fact.get("source_doc_type", "")).lower():
            # Check if we have insurance coverage for this transport (Hypothetical)
            # result["questions"].append("Vehicle transport detected but no insurance coverage confirmation found.")
            pass

checkpoint = IntelligenceCheckpoint()
