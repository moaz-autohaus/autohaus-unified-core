"""
Phase 7 - Setup for `open_questions`
Creates the schema for the Open Questions Ops Loop.
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

def setup_open_questions():
    client = get_bq_client()
    if not client:
        print("No BigQuery client available.")
        return

    # Open Questions Table
    ddl = """
    CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.open_questions` (
      question_id STRING NOT NULL,
      question_type STRING NOT NULL,
      priority STRING, -- HIGH, MEDIUM, LOW
      status STRING, -- OPEN, ASSIGNED, SNOOZED, RESOLVED, ESCALATED
      context STRING, -- JSON dumped object
      description STRING,
      assigned_to STRING,
      escalation_target STRING,
      due_by TIMESTAMP,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
      snoozed_until TIMESTAMP,
      resolved_at TIMESTAMP,
      resolution_event_id STRING
    ) CLUSTER BY status, priority;
    """
    
    try:
        client.query(ddl).result()
        print("✅ Created open_questions table")
    except Exception as e:
        print(f"❌ Failed to setup open_questions: {e}")

if __name__ == "__main__":
    setup_open_questions()
