import os
from google.cloud import bigquery
import google.auth
from dotenv import load_dotenv

# Load unified environment variables specifically targeting auth path
load_dotenv(os.path.expanduser('~/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/auth/.env'))

PROJECT_ID = "autohaus-infrastructure"
DATASET_ID = "autohaus_cil"
TABLE_ID = "system_audit_ledger"
FULL_TABLE_ID = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

def provision_lineage_log():
    print(f"[PROVISION] Creating Lineage Log / Audit Ledger: {FULL_TABLE_ID} ...")
    
    try:
        credentials, project = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform', 'https://www.googleapis.com/auth/bigquery']
        )
        
        # Impersonate Corporate Unified Identity
        if hasattr(credentials, 'with_subject'):
            credentials = credentials.with_subject('moaz@autohausia.com')
            
        client = bigquery.Client(credentials=credentials, project=PROJECT_ID)
        
        schema = [
            bigquery.SchemaField("audit_id", "STRING", mode="REQUIRED", description="A unique UUID for the audit event"),
            bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED", description="UTC timestamp of the mutation"),
            bigquery.SchemaField("actor_id", "STRING", mode="REQUIRED", description="Who performed the action (e.g. 'Gemini_v1.5', 'Admin_Ahsin')"),
            bigquery.SchemaField("action_type", "STRING", mode="REQUIRED", description="e.g., 'EXTRACTION', 'GOVERNANCE_APPROVAL', 'MANUAL_OVERRIDE'"),
            bigquery.SchemaField("entity_type", "STRING", mode="REQUIRED", description="e.g., 'VEHICLE', 'JOB_CARD', 'PERSON'"),
            bigquery.SchemaField("entity_id", "STRING", mode="REQUIRED", description="The ID of the mutated record (e.g., VIN or PR_ID)"),
            bigquery.SchemaField("old_value", "STRING", mode="NULLABLE", description="JSON string of previous state"),
            bigquery.SchemaField("new_value", "STRING", mode="NULLABLE", description="JSON string of new state or confidence score"),
            bigquery.SchemaField("metadata", "STRING", mode="NULLABLE", description="Additional context (source file paths, IP addresses)")
        ]
        
        table = bigquery.Table(FULL_TABLE_ID, schema=schema)
        # Enable time partitioning for cost efficiency and infinite scale
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="timestamp"
        )
        
        # Make the table creation idempotent
        table = client.create_table(table, exists_ok=True)
        print(f"[SUCCESS] Table {table.project}.{table.dataset_id}.{table.table_id} is provisioned and ready.")
        
    except Exception as e:
        print(f"[CRITICAL ERROR] Failed to provision Lineage Log: {str(e)}")

if __name__ == "__main__":
    provision_lineage_log()
