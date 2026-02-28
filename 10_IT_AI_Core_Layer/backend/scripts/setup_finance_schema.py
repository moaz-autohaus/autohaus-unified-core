import os
import json
from google.cloud import bigquery
from google.oauth2 import service_account

# Paths
BASE_DIR = "/Users/moazsial/Documents/AutoHaus_CIL"
KEY_PATH = os.path.join(BASE_DIR, "10_IT_AI_Core_Layer/backend/auth/replit-sa-key.json")
PROJECT_ID = "autohaus-infrastructure"
DATASET_ID = "autohaus_cil"
TABLE_ID = "financial_ledger"

def get_client():
    if not os.path.exists(KEY_PATH):
        print(f"Error: Credentials not found at {KEY_PATH}")
        return None
    with open(KEY_PATH, 'r') as f:
        key_info = json.load(f)
    credentials = service_account.Credentials.from_service_account_info(key_info)
    return bigquery.Client(credentials=credentials, project=PROJECT_ID)

def setup_ledger():
    client = get_client()
    if not client: return
    
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    
    schema = [
        bigquery.SchemaField("entry_id", "STRING", mode="REQUIRED", description="Unique ID for this specific line item"),
        bigquery.SchemaField("transaction_id", "STRING", mode="REQUIRED", description="Groups balancing DEBIT/CREDIT rows together"),
        bigquery.SchemaField("transaction_date", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("account_code", "STRING", mode="REQUIRED", description="Chart of Accounts code (e.g. 1400)"),
        bigquery.SchemaField("account_name", "STRING", mode="REQUIRED", description="e.g. Inventory - Vehicles"),
        bigquery.SchemaField("entry_type", "STRING", mode="REQUIRED", description="DEBIT or CREDIT"),
        bigquery.SchemaField("amount", "FLOAT64", mode="REQUIRED", description="Absolute positive value of the entry"),
        bigquery.SchemaField("entity_id", "STRING", mode="NULLABLE", description="VIN, Vendor ID, or Person ID this transaction directly ties to"),
        bigquery.SchemaField("description", "STRING", mode="NULLABLE", description="Memo / Narration"),
        bigquery.SchemaField("created_by", "STRING", mode="REQUIRED", description="Actor who generated this entry (SYSTEM, USER...)"),
        bigquery.SchemaField("status", "STRING", mode="REQUIRED", description="POSTED or VOIDED"),
        bigquery.SchemaField("source_document_id", "STRING", mode="NULLABLE", description="Link back to extracting OCR doc or API payload")
    ]
    
    table = bigquery.Table(table_ref, schema=schema)
    
    try:
        table = client.create_table(table, exists_ok=True)
        print(f"✅ Verified BigQuery table {table_ref} with strict Double-Entry schema.")
    except Exception as e:
        print(f"❌ Failed to create/verify table: {e}")

if __name__ == "__main__":
    setup_ledger()
