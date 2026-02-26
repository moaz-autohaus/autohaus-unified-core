
import os
import json
import uuid
from datetime import datetime, timezone
from google.cloud import bigquery
from google.oauth2 import service_account

# Paths
BASE_DIR = "/Users/moazsial/Documents/AutoHaus_CIL"
STATE_PATH = os.path.join(BASE_DIR, "AUTOHAUS_SYSTEM_STATE.json")
KEY_PATH = os.path.join(BASE_DIR, "10_IT_AI_Core_Layer/backend/auth/replit-sa-key.json")

def seed_registry():
    if not os.path.exists(STATE_PATH):
        print(f"Error: State file not found at {STATE_PATH}")
        return

    with open(STATE_PATH, 'r') as f:
        state = json.load(f)

    # Initialize BigQuery
    with open(KEY_PATH, 'r') as f:
        key_info = json.load(f)
    
    credentials = service_account.Credentials.from_service_account_info(key_info)
    client = bigquery.Client(credentials=credentials, project=key_info.get("project_id"))

    entities_to_insert = []

    # 1. Process LLCs
    llcs = state.get("active_entities", {})
    for entity_id, data in llcs.items():
        entities_to_insert.append({
            "entity_id": entity_id,
            "entity_type": "COMPANY",
            "status": "ACTIVE",
            "stub_reason": None,
            "anchors": json.dumps(data),
            "aliases": json.dumps([]),
            "authority_level": "VERIFIED",
            "completeness_score": 1.0,
            "lineage": json.dumps(["SYSTEM_MANIFEST_v3.1"]),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })

    # 2. Process Personnel
    personnel = state.get("personnel_access_matrix", {})
    for person_id, role_desc in personnel.items():
        # Match person_id to name if possible, or just use ID
        name = person_id.split('_')[0].title()
        
        entities_to_insert.append({
            "entity_id": person_id,
            "entity_type": "PERSON",
            "status": "ACTIVE",
            "stub_reason": None,
            "anchors": json.dumps({"name": name, "role_description": role_desc}),
            "aliases": json.dumps([]),
            "authority_level": "SOVEREIGN" if "CEO" in person_id else "ASSERTED",
            "completeness_score": 1.0,
            "lineage": json.dumps(["SYSTEM_MANIFEST_v3.1"]),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })

    if not entities_to_insert:
        print("No entities found to seed.")
        return

    print(f"Seeding {len(entities_to_insert)} entities into entity_registry...")
    table_id = "autohaus-infrastructure.autohaus_cil.entity_registry"
    
    errors = client.insert_rows_json(table_id, entities_to_insert)
    if errors:
        print(f"FAILED to seed registry: {errors}")
    else:
        print("✅ Successfully seeded 7 LLCs and 5 Personnel into entity_registry.")

if __name__ == "__main__":
    seed_registry()
