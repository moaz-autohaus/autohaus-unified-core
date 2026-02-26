"""
Phase 8 Schema Upgrades: Enrichment & Provenance
Adds provenance capabilities to entity_facts and creates external API ledger.
"""

import os
import json
from google.cloud import bigquery
from google.oauth2 import service_account

def get_bq_client():
    project_id = "autohaus-infrastructure"
    local_key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "auth", "replit-sa-key.json")
    if os.path.exists(local_key_path):
        credentials = service_account.Credentials.from_service_account_file(local_key_path)
        return bigquery.Client(credentials=credentials, project=project_id)
    return None

def upgrade_schema():
    client = get_bq_client()
    if not client:
        print("No BigQuery client available.")
        return

    commands = [
        # Upgrades to entity_facts
        "ALTER TABLE `autohaus-infrastructure.autohaus_cil.entity_facts` ADD COLUMN IF NOT EXISTS provenance_url STRING;",
        "ALTER TABLE `autohaus-infrastructure.autohaus_cil.entity_facts` ADD COLUMN IF NOT EXISTS provenance_reference STRING;",
        "ALTER TABLE `autohaus-infrastructure.autohaus_cil.entity_facts` ADD COLUMN IF NOT EXISTS data_tier STRING;",
        "ALTER TABLE `autohaus-infrastructure.autohaus_cil.entity_facts` ADD COLUMN IF NOT EXISTS corroboration_count INT64;",
        
        # New table: external_api_ledger
        """
        CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.external_api_ledger` (
            request_id STRING NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
            connector_name STRING NOT NULL,
            entity_id STRING,
            endpoint_url STRING,
            request_payload STRING,
            response_status INT64,
            response_payload STRING,
            cost_incurred FLOAT64 DEFAULT 0.0,
            duration_ms INT64
        ) PARTITION BY DATE(timestamp) CLUSTER BY connector_name;
        """
    ]

    for cmd in commands:
        try:
            print(f"Executing: {cmd[:60]}...")
            client.query(cmd).result()
            print("✅ Success")
        except Exception as e:
            print(f"❌ Failed: {e}")

if __name__ == "__main__":
    upgrade_schema()
