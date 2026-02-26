from typing import Dict, Any, Optional
from .base_connector import BaseConnector

class NHTSASafetyConnector(BaseConnector):
    async def get_safety_rating(self, make: str, model: str, year: str, entity_id: str) -> Dict[str, Any]:
        """
        Fetches safety ratings. Requires 2 api calls. First to get vehicle ID, then to get rating.
        """
        # Step 1: Get Vehicle ID
        url_id = f"https://api.nhtsa.gov/SafetyRatings/modelyear/{year}/make/{make}/model/{model}"
        data_id = await self.fetch(url_id, entity_id=entity_id)
        
        if "error" in data_id or not data_id.get("Results"):
            return {"source": "NHTSA_SAFETY", "error": "Vehicle ID not found"}
            
        vehicle_id = data_id["Results"][0]["VehicleId"]
        
        # Step 2: Get Ratings
        url_rating = f"https://api.nhtsa.gov/SafetyRatings/VehicleId/{vehicle_id}"
        data_rating = await self.fetch(url_rating, entity_id=entity_id)
        
        if "error" in data_rating or not data_rating.get("Results"):
            return {"source": "NHTSA_SAFETY", "error": "Ratings not found"}
            
        ratings = data_rating["Results"][0]
        
        return {
            "source": "NHTSA_SAFETY",
            "provenance_url": f"https://www.nhtsa.gov/vehicle/{year}/{make}/{model}",
            "overall_rating": ratings.get("OverallRating"),
            "frontal_crash_rating": ratings.get("OverallFrontCrashRating"),
            "side_crash_rating": ratings.get("OverallSideCrashRating"),
            "rollover_rating": ratings.get("RolloverRating")
        }
