
import os
import json
from google.cloud import bigquery
from google.oauth2 import service_account

KEY_PATH = "/Users/moazsial/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/backend/auth/replit-sa-key.json"

def test_bq_auth():
    if not os.path.exists(KEY_PATH):
        print(f"ERROR: Key not found at {KEY_PATH}")
        return

    try:
        with open(KEY_PATH, 'r') as f:
            info = json.load(f)
        
        credentials = service_account.Credentials.from_service_account_info(info)
        client = bigquery.Client(credentials=credentials, project=info.get("project_id"))
        
        print(f"Successfully initialized client for project: {client.project}")
        
        # Try a simple operation
        datasets = list(client.list_datasets())
        print(f"Found {len(datasets)} datasets.")
        for ds in datasets:
            print(f" - {ds.dataset_id}")
            
    except Exception as e:
        print(f"AUTH ERROR: {e}")

if __name__ == "__main__":
    test_bq_auth()
