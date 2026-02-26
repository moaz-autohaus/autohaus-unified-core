"""
Phase 7 - Setup for `entity_facts` and `entity_trust_summary` view
Creates the central truth projection layer.
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

def setup_facts():
    client = get_bq_client()
    if not client:
        print("No BigQuery client available.")
        return

    # Facts Table
    ddl_facts = """
    CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.entity_facts` (
      entity_id STRING NOT NULL,
      entity_type STRING NOT NULL,
      field_name STRING NOT NULL,
      value STRING,
      confidence_score FLOAT64,
      source_document_id STRING,
      source_type STRING,
      status STRING, -- ACTIVE, CONFLICTING_CLAIM, RESOLVED
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
    ) CLUSTER BY entity_id, field_name;
    """
    
    # Trust Summary View (Pivot using any_value, ordered by confidence)
    # This is a simplified v1 pivot
    ddl_view = """
    CREATE OR REPLACE VIEW `autohaus-infrastructure.autohaus_cil.entity_trust_summary` AS
    SELECT 
        entity_id,
        entity_type,
        MAX(CASE WHEN field_name = 'vin' THEN value END) as vin,
        MAX(CASE WHEN field_name = 'make' THEN value END) as make,
        MAX(CASE WHEN field_name = 'model' THEN value END) as model,
        MAX(CASE WHEN field_name = 'year' THEN value END) as year,
        AVG(confidence_score) as avg_trust_score,
        COUNTIF(status = 'CONFLICTING_CLAIM') as open_conflicts
    FROM `autohaus-infrastructure.autohaus_cil.entity_facts`
    GROUP BY entity_id, entity_type
    """
    
    try:
        client.query(ddl_facts).result()
        print("✅ Created entity_facts table")
        client.query(ddl_view).result()
        print("✅ Created entity_trust_summary view")
    except Exception as e:
        print(f"❌ Failed to setup facts: {e}")

if __name__ == "__main__":
    setup_facts()
