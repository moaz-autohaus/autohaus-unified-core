import asyncio
import os
import sys
import json
from google.cloud import bigquery
from google.oauth2 import service_account

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from enrichment.enrichment_engine import EnrichmentEngine

def get_bq_client():
    project_id = "autohaus-infrastructure"
    local_key_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "auth", "replit-sa-key.json")
    if os.path.exists(local_key_path):
        credentials = service_account.Credentials.from_service_account_file(local_key_path)
        return bigquery.Client(credentials=credentials, project=project_id)
    return None

async def test_enrichment():
    bq = get_bq_client()
    if not bq:
        print("No BigQuery credentials.")
        return

    # A widely known sample VIN (e.g., standard BMW or Ford for testing)
    # Let's just use the fake one we test with: WBA93HM0XP1234567 
    # Or a real one if you have it. Let's use a real-like pattern typical for a 2021 Ford F-150: 1FTFW1ED...
    # We will use "1VWBT7A34C0XXXXXX" (Volkswagon Jetta 2012)
    # Or just let NHTSA figure out whatever part it can
    test_vin = "1VWBT7A34C0879555" 
    entity_id = "VEH_TEST_ENRICH_01"

    engine = EnrichmentEngine(bq)
    
    print(f"🚀 Triggering Enrichment for VIN: {test_vin} ...")
    result = await engine.enrich(
        entity_type="VEHICLE", 
        entity_id=entity_id, 
        trigger="MANUAL_TEST", 
        primary_key=test_vin
    )
    
    print("\n✅ ENRICHMENT COMPLETE:")
    print(json.dumps(result, indent=2))
    
    print("\n🔍 Checking resulting facts in BigQuery...")
    query = f"""
        SELECT field_name, value, confidence_score, data_tier, provenance_url
        FROM `autohaus-infrastructure.autohaus_cil.entity_facts`
        WHERE entity_id = '{entity_id}'
        ORDER BY data_tier ASC
    """
    rows = bq.query(query).result()
    for row in rows:
        print(f"[{row.data_tier}] {row.field_name}: {row.value}")
        print(f"   ↳ Confidence Score: {row.confidence_score}")
        print(f"   ↳ Source: {row.provenance_url}")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(test_enrichment())
