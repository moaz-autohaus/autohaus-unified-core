from typing import Dict, Any, Optional
from .base_connector import BaseConnector

class NHTSAComplaintsConnector(BaseConnector):
    async def get_complaints(self, make: str, model: str, year: str, entity_id: str) -> Dict[str, Any]:
        """
        Fetches complaints from NHTSA API.
        """
        url = f"https://api.nhtsa.gov/complaints/complaintsByVehicle"
        params = {
            "make": make,
            "model": model,
            "modelYear": year
        }
        
        data = await self.fetch(url, params=params, entity_id=entity_id)
        if "error" in data:
            return data
            
        results = data.get("results", [])
        
        return {
            "source": "NHTSA_COMPLAINTS",
            "provenance_url": f"https://www.nhtsa.gov/vehicle/{year}/{make}/{model}#complaints",
            "count": data.get("count", len(results)),
            "complaints": results[:5]  # Keep only top 5 for facts
        }
