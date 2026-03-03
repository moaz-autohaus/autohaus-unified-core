
import logging
from typing import List, Dict, Any, Optional
from google.cloud import bigquery

logger = logging.getLogger("autohaus.cil.policy_engine")

class PolicyEngineCIL:
    """
    CIL Layer: Computes thresholds and detects breaches.
    Exclusive source of truth for enforcement signals.
    """
    def __init__(self, bq_client=None):
        from database.bigquery_client import BigQueryClient
        self.bq = bq_client or BigQueryClient()

    async def detect_breaches(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Interrogates CIL projections for active conflicts or policy breaches.
        CIL side: Pure truth detection.
        """
        if not self.bq.client:
            return []
            
        query = f"""
            SELECT 'CONFLICT' as type, claim_id as block_id, target_field as reason
            FROM `autohaus-infrastructure.autohaus_cil.pending_verification_queue`
            WHERE target_id = @entity_id AND truth_status = 'CONFLICT'
            UNION ALL
            SELECT 'BREACH' as type, event_id as block_id, event_type as reason
            FROM `autohaus-infrastructure.autohaus_cil.compliance_timeline`
            WHERE target_id = @entity_id AND event_type = 'THRESHOLD_BREACHED'
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("entity_id", "STRING", entity_id)]
        )
        
        try:
            results = list(self.bq.client.query(query, job_config=job_config).result())
            return [{"type": r.type, "block_id": r.block_id, "reason": r.reason} for r in results]
        except Exception as e:
            logger.debug(f"[POLICY_CIL] Truth lookup failed for {entity_id}: {e}")
            return []
            
    def compute_threshold_violation(self, domain: str, key: str, value: float) -> bool:
        """
        CIL side: evaluates if a value violates a registered policy threshold.
        """
        from database.policy_engine import get_policy
        threshold = float(get_policy(domain, key) or 0)
        return value > threshold
