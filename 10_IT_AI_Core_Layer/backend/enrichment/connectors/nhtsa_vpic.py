from typing import Dict, Any, Optional
from .base_connector import BaseConnector

class NHTSAVpicConnector(BaseConnector):
    async def get_vin_specs(self, vin: str, entity_id: str) -> Dict[str, Any]:
        """
        Fetches vehicle specifications from NHTSA vPIC using the VIN.
        """
        url = f"https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{vin}"
        params = {"format": "json"}
        
        data = await self.fetch(url, params=params, entity_id=entity_id)
        if "error" in data:
            return data
            
        results = data.get("Results", [])
        
        # Soft-mapping: keep the structured high value stuff but return dict
        specs = {}
        target_keys = {
            "Model Year": "year",
            "Make": "make",
            "Model": "model",
            "Trim": "trim",
            "Body Class": "body_class",
            "Engine Number of Cylinders": "engine_cylinders",
            "Displacement (L)": "engine_displacement_l",
            "Drive Type": "drive_type",
            "Fuel Type - Primary": "fuel_type",
            "Transmission Style": "transmission",
            "Doors": "doors",
            "Manufacturer Name": "manufacturer",
            "Plant Country": "plant_country",
            "Plant State": "plant_state",
            "Gross Vehicle Weight Rating From": "gvwr",
            "Vehicle Type": "vehicle_type"
        }
        
        for item in results:
            variable = item.get("Variable")
            value = item.get("Value")
            if variable in target_keys and value is not None and value != "":
                specs[target_keys[variable]] = value
                
        return {
            "source": "NHTSA_VPIC",
            "provenance_url": f"https://vpic.nhtsa.dot.gov/decoder/Decoder/VINDetail/{vin}",
            "specs": specs,
            "raw": data
        }
