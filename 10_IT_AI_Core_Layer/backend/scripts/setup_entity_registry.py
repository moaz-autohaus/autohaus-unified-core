"""
Phase 7 - Setup for `entity_registry`
Creates the central entity registry table.
"""

import os
import json
from google.cloud import bigquery
from google.oauth2 import service_account

def get_bq_client():
    project_id = "autohaus-infrastructure"
    sa_json_str = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    if sa_json_str:
        try:
            sa_info = json.loads(sa_json_str)
            credentials = service_account.Credentials.from_service_account_info(sa_info)
            return bigquery.Client(credentials=credentials, project=project_id)
        except Exception as e:
            print(f"Failed to parse GCP_SERVICE_ACCOUNT_JSON: {e}")
            
    local_key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "auth", "replit-sa-key.json")
    if os.path.exists(local_key_path):
        credentials = service_account.Credentials.from_service_account_file(local_key_path)
        return bigquery.Client(credentials=credentials, project=project_id)
    return None

def setup_registry():
    client = get_bq_client()
    if not client:
        print("No BigQuery client available.")
        return

    ddl = """
    CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.entity_registry` (
      entity_id STRING NOT NULL,
      entity_type STRING NOT NULL, -- VEHICLE, PERSON, VENDOR, COMPANY
      canonical_name STRING,
      status STRING NOT NULL, -- STUB, ACTIVE, ARCHIVED, MERGED
      stub_reason STRING,
      anchors STRING, -- JSON string representation
      aliases STRING, -- JSON array representation
      authority_level STRING, 
      completeness_score FLOAT64,
      lineage STRING, -- JSON array of source document IDs
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
    ) CLUSTER BY entity_type, status;
    """
    try:
        client.query(ddl).result()
        print("✅ Created entity_registry table")
    except Exception as e:
        print(f"❌ Failed to create table: {e}")

if __name__ == "__main__":
    setup_registry()
