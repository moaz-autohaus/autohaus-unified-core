import os
from google.cloud import bigquery
import google.auth
from dotenv import load_dotenv

load_dotenv(os.path.expanduser('~/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/auth/.env'))

PROJECT_ID = "autohaus-infrastructure"
DATASET_ID = "autohaus_cil"
TABLE_ID = "master_person_graph"
FULL_TABLE_ID = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

def provision_identity_graph():
    print(f"[PROVISION] Creating Universal Identity Graph: {FULL_TABLE_ID} ...")
    
    try:
        credentials, project = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform', 'https://www.googleapis.com/auth/bigquery']
        )
        
        # Impersonate Corporate Unified Identity
        if hasattr(credentials, 'with_subject'):
            credentials = credentials.with_subject('moaz@autohausia.com')
            
        client = bigquery.Client(credentials=credentials, project=PROJECT_ID)
        
        # Schema for the Human Graph
        schema = [
            bigquery.SchemaField("master_person_id", "STRING", mode="REQUIRED", description="Universal ID across all systems (UUID)"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED", description="When the entity was first seen"),
            bigquery.SchemaField("last_seen", "TIMESTAMP", mode="REQUIRED", description="Last touchpoint interaction timestamp"),
            bigquery.SchemaField("primary_email", "STRING", mode="NULLABLE", description="Primary matched email for communication"),
            bigquery.SchemaField("primary_phone", "STRING", mode="NULLABLE", description="E.164 formatted phone number"),
            bigquery.SchemaField("first_name", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("last_name", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("aliases", "STRING", mode="NULLABLE", description="JSON array of alternative names/spellings"),
            bigquery.SchemaField("connected_vins", "STRING", mode="NULLABLE", description="JSON array of owned/serviced/rented vehicle VINs"),
            bigquery.SchemaField("entity_tags", "STRING", mode="NULLABLE", description="JSON array of categorical tags (e.g. ['LANE_A_BUYER', 'FLUIDITRUCK_RENTER'])"),
            bigquery.SchemaField("confidence_score", "FLOAT", mode="REQUIRED", description="0-1.0 AI Confidence that this entity is accurately merged")
        ]
        
        table = bigquery.Table(FULL_TABLE_ID, schema=schema)
        
        # Make the table creation idempotent
        table = client.create_table(table, exists_ok=True)
        print(f"[SUCCESS] Identity Graph {table.project}.{table.dataset_id}.{table.table_id} is provisioned.")
        
    except Exception as e:
        print(f"[CRITICAL ERROR] Failed to provision Identity Graph: {str(e)}")

if __name__ == "__main__":
    provision_identity_graph()
