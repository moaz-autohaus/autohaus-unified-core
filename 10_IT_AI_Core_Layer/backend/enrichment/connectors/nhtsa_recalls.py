from typing import Dict, Any, Optional
from .base_connector import BaseConnector

class NHTSARecallsConnector(BaseConnector):
    async def get_recalls(self, make: str, model: str, year: str, entity_id: str) -> Dict[str, Any]:
        """
        Fetches safety recalls from NHTSA API.
        """
        url = f"https://api.nhtsa.gov/recalls/recallsByVehicle"
        params = {
            "make": make,
            "model": model,
            "modelYear": year
        }
        
        data = await self.fetch(url, params=params, entity_id=entity_id)
        if "error" in data:
            return data
            
        results = data.get("results", [])
        
        recalls = []
        for item in results:
            recalls.append({
                "campaign_number": item.get("NHTSACampaignNumber"),
                "component": item.get("Component"),
                "summary": item.get("Summary"),
                "consequence": item.get("Conequence"), # Typo in their API usually
                "remedy": item.get("Remedy")
            })
            
        return {
            "source": "NHTSA_RECALLS",
            "provenance_url": f"https://www.nhtsa.gov/recalls",
            "recalls": recalls,
            "count": len(recalls)
        }
