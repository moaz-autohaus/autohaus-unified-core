import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List

from .connectors.nhtsa_vpic import NHTSAVpicConnector
from .connectors.nhtsa_recalls import NHTSARecallsConnector
from .connectors.nhtsa_complaints import NHTSAComplaintsConnector
from .connectors.nhtsa_safety import NHTSASafetyConnector

logger = logging.getLogger("autohaus.enrichment.vin")

class VinEnrichmentCascade:
    def __init__(self, bq_client):
        self.bq_client = bq_client
        self.vpic = NHTSAVpicConnector(bq_client)
        self.recalls = NHTSARecallsConnector(bq_client)
        self.complaints = NHTSAComplaintsConnector(bq_client)
        self.safety = NHTSASafetyConnector(bq_client)

    async def enrich_vehicle(self, entity_id: str, vin: str) -> Dict[str, Any]:
        """Runs the enrichment cascade for a VIN."""
        results = {
            "entity_id": entity_id,
            "vin": vin,
            "sources_queried": ["NHTSA_VPIC", "NHTSA_RECALLS", "NHTSA_COMPLAINTS", "NHTSA_SAFETY"],
            "sources_succeeded": [],
            "sources_failed": [],
            "facts_generated": [],
            "digital_twin_flags": []
        }
        
        # Step 1: Decode VIN (Sequential, as it gives us Year/Make/Model)
        vpic_data = await self.vpic.get_vin_specs(vin, entity_id)
        if "error" in vpic_data:
            results["sources_failed"].append("NHTSA_VPIC")
            return results  # Stop here if we can't decode the VIN
            
        results["sources_succeeded"].append("NHTSA_VPIC")
        specs = vpic_data.get("specs", {})
        
        # Add basic specs as facts (TIER_1 or TIER_3)
        for key, value in specs.items():
            tier = "TIER_1_SURFACE" if key in ["year", "make", "model", "trim"] else "TIER_3_DEEP"
            results["facts_generated"].append({
                "field_name": key,
                "value": str(value),
                "fact_category": "SPECS",
                "authority_level": "AUTO_ENRICHED",
                "confidence_score": 0.95,
                "provenance_url": vpic_data.get("provenance_url"),
                "data_tier": tier
            })

        # Need year/make/model for the next APIs
        year = specs.get("year")
        make = specs.get("make")
        model = specs.get("model")
        
        if not (year and make and model):
            return results

        # Step 2: Fire subsequent API calls concurrently
        tasks = [
            self.recalls.get_recalls(make, model, year, entity_id),
            self.complaints.get_complaints(make, model, year, entity_id),
            self.safety.get_safety_rating(make, model, year, entity_id)
        ]
        parallel_results = await asyncio.gather(*tasks)

        recalls_data, complaints_data, safety_data = parallel_results

        # Handle Recalls
        if "error" not in recalls_data:
            results["sources_succeeded"].append("NHTSA_RECALLS")
            count = recalls_data.get("count", 0)
            results["facts_generated"].append({
                "field_name": "open_recalls",
                "value": str(count),
                "fact_category": "SAFETY",
                "authority_level": "AUTO_ENRICHED",
                "confidence_score": 0.95,
                "provenance_url": recalls_data.get("provenance_url"),
                "data_tier": "TIER_2_OPERATIONAL"
            })
            if count > 0:
                results["digital_twin_flags"].append({
                    "severity": "YELLOW",
                    "description": f"{count} open NHTSA recall(s) found.",
                    "category": "COMPLIANCE"
                })
        else:
            results["sources_failed"].append("NHTSA_RECALLS")

        # Handle Complaints
        if "error" not in complaints_data:
            results["sources_succeeded"].append("NHTSA_COMPLAINTS")
            results["facts_generated"].append({
                "field_name": "historical_complaints",
                "value": str(complaints_data.get("count", 0)),
                "fact_category": "SAFETY",
                "authority_level": "AUTO_ENRICHED",
                "confidence_score": 0.90,
                "provenance_url": complaints_data.get("provenance_url"),
                "data_tier": "TIER_3_DEEP"
            })
        else:
            results["sources_failed"].append("NHTSA_COMPLAINTS")

        # Handle Safety
        if "error" not in safety_data:
            results["sources_succeeded"].append("NHTSA_SAFETY")
            results["facts_generated"].append({
                "field_name": "nhtsa_overall_rating",
                "value": str(safety_data.get("overall_rating", "Not Rated")),
                "fact_category": "SAFETY",
                "authority_level": "AUTO_ENRICHED",
                "confidence_score": 0.95,
                "provenance_url": safety_data.get("provenance_url"),
                "data_tier": "TIER_1_SURFACE"
            })
        else:
            results["sources_failed"].append("NHTSA_SAFETY")

        return results
