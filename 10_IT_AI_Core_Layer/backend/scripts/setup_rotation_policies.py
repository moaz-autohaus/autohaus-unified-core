import os
import sys
import json
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.bigquery_client import BigQueryClient

def setup_rotation_policies():
    bq = BigQueryClient()
    client = bq.client
    if not client:
        print("Failed to initialize BigQuery client. Reauthentication may be required.")
        return

    policies = [
        {
            "domain": "SECURITY",
            "key": "security_key_rotation_requires_confirmation",
            "value": "true",
            "active": True,
            "version": int(datetime.utcnow().timestamp()),
            "created_at": datetime.utcnow().isoformat()
        },
        {
            "domain": "SECURITY",
            "key": "rotation_sms_recipient",
            "value": "MOAZ_SOVEREIGN",
            "active": True,
            "version": int(datetime.utcnow().timestamp()),
            "created_at": datetime.utcnow().isoformat()
        },
        {
            "domain": "SECURITY",
            "key": "credential_rotated_event_retention",
            "value": "10",
            "active": True,
            "version": int(datetime.utcnow().timestamp()),
            "created_at": datetime.utcnow().isoformat()
        },
        {
            "domain": "SECURITY",
            "key": "terminal_clear_delay_seconds",
            "value": "30",
            "active": True,
            "version": int(datetime.utcnow().timestamp()),
            "created_at": datetime.utcnow().isoformat()
        }
    ]

    table_id = f"{bq.project_id}.{bq.dataset_id}.policy_registry"
    
    # Check for existing policies to avoid duplicates (idempotency)
    existing_q = f"SELECT domain, key FROM `{table_id}` WHERE domain = 'SECURITY'"
    try:
        existing_rows = [(row.domain, row.key) for row in client.query(existing_q).result()]
    except Exception as e:
        existing_rows = []
        print(f"Could not fetch existing policies: {e}")

    to_insert = []
    for p in policies:
        if (p["domain"], p["key"]) not in existing_rows:
            to_insert.append(p)

    if to_insert:
        errors = client.insert_rows_json(table_id, to_insert)
        if errors:
            print(f"Errors occurred during policy seeding: {errors}")
        else:
            print(f"Successfully seeded {len(to_insert)} security policies.")
    else:
        print("Security policies already exist.")

if __name__ == "__main__":
    setup_rotation_policies()
