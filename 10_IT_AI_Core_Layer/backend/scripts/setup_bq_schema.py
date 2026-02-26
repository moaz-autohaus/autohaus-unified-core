import os
from google.cloud import bigquery
from google.oauth2 import service_account

def get_bq_client():
    project_id = "autohaus-infrastructure"
    sa_json_str = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    
    if sa_json_str:
        try:
            import json
            sa_info = json.loads(sa_json_str)
            credentials = service_account.Credentials.from_service_account_info(sa_info)
            return bigquery.Client(credentials=credentials, project=project_id)
        except Exception as e:
            print(f"Failed to parse GCP_SERVICE_ACCOUNT_JSON from environment: {e}")
            return None
    else:
        # Fallback
        local_key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "auth", "replit-sa-key.json")
        if os.path.exists(local_key_path):
            credentials = service_account.Credentials.from_service_account_file(local_key_path)
            return bigquery.Client(credentials=credentials, project=project_id)
        else:
            print("No credentials found.")
            return None

def execute_ddl():
    client = get_bq_client()
    if not client:
        print("Could not get BigQuery client. Aborting schema setup.")
        return

    # Dataset Creation/Verification (Assuming dataset autohaus_cil already exists, but we ensure tables)
    
    ddl_statements = [
        """
        CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.documents` (
          document_id STRING NOT NULL,
          content_hash STRING NOT NULL,
          filename_original STRING,
          detected_format STRING,
          drive_file_id STRING,
          archive_path STRING,
          doc_type STRING,
          classification_confidence FLOAT64,
          authority_level STRING DEFAULT 'ADVISORY',
          version INT64 DEFAULT 1,
          version_group_id STRING,
          latest_version BOOL DEFAULT TRUE,
          amendment_lock BOOL DEFAULT FALSE,
          terminal_state STRING DEFAULT 'INGESTED' NOT NULL,
          requires_human_review BOOL DEFAULT FALSE,
          kamm_compliance_type BOOL DEFAULT FALSE,
          ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
        ) PARTITION BY DATE(ingested_at) CLUSTER BY doc_type, terminal_state;
        """
    ]

    for ddl in ddl_statements:
        print(f"Executing DDL:\n{ddl.strip().splitlines()[0]}...")
        try:
            job = client.query(ddl)
            job.result()  # Wait for completion
            print("Success.")
        except Exception as e:
            print(f"Failed to execute DDL: {e}")
            
if __name__ == "__main__":
    execute_ddl()
