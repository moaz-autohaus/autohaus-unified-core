"""
AutoHaus CIL — Native Governance Policy Engine
Phase 7 (D1)

Provides a single source of truth for all business rules, thresholds, and logic.
Values are stored in BQ (policy_registry) and cached in-memory with a TTL.
"""

import json
import logging
import time
from typing import Optional, Any
from .bigquery_client import BigQueryClient

logger = logging.getLogger("autohaus.policy")

class PolicyEngine:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PolicyEngine, cls).__new__(cls)
            cls._instance._cache = {}
            cls._instance._cache_ttl = 300  # 5 minutes
            cls._instance.bq_client = BigQueryClient()
        return cls._instance

    def _get_cache_key(self, domain: str, key: str) -> str:
        return f"{domain}::{key}"

    def _fetch_from_bq(self, domain: str, key: str):
        """Fetches all active policies for a domain/key from BQ."""
        if not self.bq_client.client:
            logger.error("No BQ client available for PolicyEngine.")
            return []

        query = f"""
            SELECT 
                value, 
                applies_to_entity, 
                applies_to_doc_type, 
                applies_to_entity_type,
                version
            FROM `{self.bq_client.project_id}.{self.bq_client.dataset_id}.policy_registry`
            WHERE domain = @domain 
              AND key = @key 
              AND active = TRUE
            ORDER BY version DESC
        """
        
        from google.cloud import bigquery
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("domain", "STRING", domain),
                bigquery.ScalarQueryParameter("key", "STRING", key),
            ]
        )
        
        try:
            results = list(self.bq_client.client.query(query, job_config=job_config))
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Failed to fetch policy {domain}.{key}: {e}")
            return []

    def get_policy(self, domain: str, key: str, doc_type: str = None, entity_type: str = None, entity: str = None) -> Any:
        """
        Get a governed policy value.
        Precedence:
          1. exact entity match
          2. doc_type match
          3. entity_type match
          4. Global (all NULLs)
        """
        cache_key = self._get_cache_key(domain, key)
        now = time.time()
        
        if cache_key not in self._cache or (now - self._cache[cache_key]['timestamp'] > self._cache_ttl):
            # Cache miss or expired
            policies = self._fetch_from_bq(domain, key)
            self._cache[cache_key] = {
                'timestamp': now,
                'policies': policies
            }
        
        policies = self._cache[cache_key]['policies']
        
        if not policies:
            # Fallback/missing policy behavior
            logger.warning(f"[POLICY MISSING] no active policy for {domain}.{key}")
            return None

        # Resolve precedence
        # We find the best matching policy
        best_match = None
        best_score = -1 # -1 means no match yet, 0=global, 1=entity_type, 2=doc_type, 3=entity

        for p in policies:
            # Parse value
            try:
                val = json.loads(p['value']) if isinstance(p['value'], str) else p['value']
            except:
                val = p['value']

            # Check applicability
            p_ent = p.get('applies_to_entity')
            p_doc = p.get('applies_to_doc_type')
            p_ent_type = p.get('applies_to_entity_type')

            score = 0 # Assume global
            
            if p_ent or p_doc or p_ent_type:
                # Specific policy
                if p_ent and p_ent == entity:
                    score = 3
                elif p_doc and p_doc == doc_type:
                    score = 2
                elif p_ent_type and p_ent_type == entity_type:
                    score = 1
                else:
                    # Specific policy but doesn't match our context. Skip.
                    continue
            
            # If we beat our best score, or if same score but higher version (already sorted by version DESC, so first seen is highest)
            if score > best_score:
                best_score = score
                best_match = val
                
            if best_score == 3:
                break # Can't get better than exact entity match

        return best_match

    def clear_cache(self):
        """Forces cache clear. Useful after HITL policy update."""
        self._cache.clear()

# Global singleton helper
_engine = PolicyEngine()

def get_policy(domain: str, key: str, doc_type: str = None, entity_type: str = None, entity: str = None) -> Any:
    return _engine.get_policy(domain, key, doc_type, entity_type, entity)

