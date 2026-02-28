import logging
from typing import Dict, Any, Optional
from .base_connector import BaseConnector

logger = logging.getLogger("autohaus.enrichment.market_data")

class MarketDataConnector(BaseConnector):
    """
    Abstract interface for market data providers.
    Each implementation provides wholesale, retail, and trade values
    for a given VIN or year/make/model/trim/mileage.
    """
    
    @property
    def source_name(self) -> str:
        return "CIL_MARKET_DATA_STUB"

    async def get_values(self, entity_id: str, vin: Optional[str] = None, 
                         year: Optional[int] = None, make: Optional[str] = None, 
                         model: Optional[str] = None, trim: Optional[str] = None, 
                         mileage: Optional[int] = None) -> Dict[str, Any]:
        """
        Returns Market data estimates.
        """
        
        # Simulate an API call cost (free for stub)
        self.log_api_call(
            target_system=self.source_name,
            endpoint="/api/v1/valuation",
            method="GET",
            entity_id=entity_id,
            status_code=200,
            latency_ms=10,
            estimated_cost=0.00
        )
        
        # Stub response matching the expected interface
        return {
            "source": self.source_name,
            "wholesale_value": None,
            "retail_value": None,
            "trade_value": None,
            "confidence": 0.0,
            "sample_size": 0,
            "note": "No market data source configured in Phase 8 MVP.",
            "error": "NotImplemented"
        }
