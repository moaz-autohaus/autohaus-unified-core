"""
AutoHaus CIL — Native Governance Relationship Validator (Pass 7)
"""

import logging
import time
from .bigquery_client import BigQueryClient

logger = logging.getLogger("autohaus.validator")

class RelationshipValidator:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RelationshipValidator, cls).__new__(cls)
            cls._instance._cache = set()
            cls._instance.bq_client = BigQueryClient()
            cls._instance._last_fetch = 0
            cls._instance._ttl = 300
        return cls._instance

    def _fetch_edges(self):
        now = time.time()
        if now - self._last_fetch < self._ttl and self._cache:
            return self._cache

        if not self.bq_client.client:
            return self._cache

        query = """
            SELECT relationship_type, source_type, target_type
            FROM `autohaus-infrastructure.autohaus_cil.relationship_type_registry`
            WHERE active = TRUE
        """
        try:
            results = list(self.bq_client.client.query(query).result())
            valid_edges = set()
            for r in results:
                valid_edges.add((r.source_type, r.target_type, r.relationship_type))
            self._cache = valid_edges
            self._last_fetch = now
        except Exception as e:
            logger.error(f"[VALIDATION] Failed to fetch relationship registry: {e}")
        return self._cache

    def validate_edge(self, source_type: str, target_type: str, relationship_type: str) -> bool:
        edges = self._fetch_edges()
        if not edges:
            logger.warning("[VALIDATION] No edges in cache, returning True (fail-open)")
            return True
            
        return (source_type, target_type, relationship_type) in edges

_validator = RelationshipValidator()

def is_valid_edge(source_type: str, target_type: str, relationship_type: str) -> bool:
    return _validator.validate_edge(source_type, target_type, relationship_type)
