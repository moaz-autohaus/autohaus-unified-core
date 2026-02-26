"""Quick verification: list all tables in autohaus_cil dataset."""
import os, sys, json
from google.cloud import bigquery
from google.oauth2 import service_account

key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "auth", "replit-sa-key.json")
credentials = service_account.Credentials.from_service_account_file(key_path)
client = bigquery.Client(credentials=credentials, project="autohaus-infrastructure")

tables = list(client.list_tables("autohaus-infrastructure.autohaus_cil"))
print(f"\n{'='*60}")
print(f"Tables in autohaus-infrastructure.autohaus_cil ({len(tables)} total):")
print(f"{'='*60}")
for t in tables:
    table_obj = client.get_table(t.reference)
    print(f"  ✅ {t.table_id:<30} rows: {table_obj.num_rows}")
print(f"{'='*60}\n")
