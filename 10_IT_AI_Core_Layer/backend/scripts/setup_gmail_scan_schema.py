import os
import json
from google.cloud import bigquery
from google.oauth2 import service_account

# Paths
BASE_DIR = "/Users/moazsial/Documents/AutoHaus_CIL"
KEY_PATH = os.path.join(BASE_DIR, "10_IT_AI_Core_Layer/backend/auth/replit-sa-key.json")
PROJECT_ID = "autohaus-infrastructure"
DATASET_ID = "autohaus_cil"

def get_client():
    if not os.path.exists(KEY_PATH):
        print(f"Error: Credentials not found at {KEY_PATH}")
        return None
    with open(KEY_PATH, 'r') as f:
        key_info = json.load(f)
    credentials = service_account.Credentials.from_service_account_info(key_info)
    return bigquery.Client(credentials=credentials, project=PROJECT_ID)

def setup_gmail_scan_tables():
    client = get_client()
    if not client: return
    
    # 1. gmail_scan_results
    results_table_id = f"{PROJECT_ID}.{DATASET_ID}.gmail_scan_results"
    results_schema = [
        bigquery.SchemaField("message_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("thread_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("email_account", "STRING", mode="REQUIRED", description="e.g. ahsin@autohausia.com"),
        bigquery.SchemaField("from_address", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("from_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("to_address", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("subject", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("date", "TIMESTAMP", mode="REQUIRED", description="Original email Date header"),
        bigquery.SchemaField("classification", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("confidence", "FLOAT", mode="REQUIRED"),
        bigquery.SchemaField("has_attachments", "BOOLEAN", mode="REQUIRED"),
        bigquery.SchemaField("attachment_types", "STRING", mode="REPEATED"),
        bigquery.SchemaField("attachment_names", "STRING", mode="REPEATED"),
        bigquery.SchemaField("body_snippet", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("extracted_entities", "JSON", mode="NULLABLE", description="VINs, dollars, companies, etc."),
        bigquery.SchemaField("scan_batch_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("processed_at", "TIMESTAMP", mode="REQUIRED")
    ]
    
    table_results = bigquery.Table(results_table_id, schema=results_schema)
    client.create_table(table_results, exists_ok=True)
    print(f"✅ Table {results_table_id} verified.")

    # 2. gmail_scan_patterns
    patterns_table_id = f"{PROJECT_ID}.{DATASET_ID}.gmail_scan_patterns"
    patterns_schema = [
        bigquery.SchemaField("batch_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("analysis_timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("pattern_data", "JSON", mode="REQUIRED"),
        bigquery.SchemaField("insight_summary", "STRING", mode="NULLABLE")
    ]
    table_patterns = bigquery.Table(patterns_table_id, schema=patterns_schema)
    client.create_table(table_patterns, exists_ok=True)
    print(f"✅ Table {patterns_table_id} verified.")

if __name__ == "__main__":
    setup_gmail_scan_tables()
