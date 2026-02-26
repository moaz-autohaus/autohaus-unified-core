import uuid
import time
import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("autohaus.enrichment.connector")

class BaseConnector:
    def __init__(self, bq_client=None):
        self.bq_client = bq_client
        self.connector_name = self.__class__.__name__

    async def fetch(self, endpoint_url: str, params: Optional[Dict] = None, entity_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Standard fetch method that logs the request and response to external_api_ledger
        """
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(endpoint_url, params=params)
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Log to ledger
                self._log_api_call(
                    request_id=request_id,
                    entity_id=entity_id,
                    endpoint_url=str(response.url),
                    request_payload=str(params) if params else "",
                    response_status=response.status_code,
                    response_payload=response.text[:2000],  # Truncate for ledger
                    cost_incurred=0.0,  # Override in paid connectors
                    duration_ms=duration_ms
                )
                
                response.raise_for_status()
                return response.json()
                
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                self._log_api_call(
                    request_id=request_id,
                    entity_id=entity_id,
                    endpoint_url=endpoint_url,
                    request_payload=str(params) if params else "",
                    response_status=500,
                    response_payload=str(e),
                    cost_incurred=0.0,
                    duration_ms=duration_ms
                )
                logger.error(f"[{self.connector_name}] Fetch failed: {e}")
                return {"error": str(e)}

    def _log_api_call(self, request_id, entity_id, endpoint_url, request_payload, response_status, response_payload, cost_incurred, duration_ms):
        if not self.bq_client:
            return
            
        row = {
            "request_id": request_id,
            "connector_name": self.connector_name,
            "entity_id": entity_id,
            "endpoint_url": endpoint_url,
            "request_payload": request_payload,
            "response_status": response_status,
            "response_payload": response_payload,
            "cost_incurred": cost_incurred,
            "duration_ms": duration_ms
        }
        
        try:
            self.bq_client.insert_rows_json(
                "autohaus-infrastructure.autohaus_cil.external_api_ledger",
                [row]
            )
        except Exception as e:
            logger.error(f"Failed to log API call to ledger: {e}")
