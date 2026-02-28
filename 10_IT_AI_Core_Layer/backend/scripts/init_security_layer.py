
import os
from google.cloud import bigquery
from database.bigquery_client import BigQueryClient

def init_security_layer():
    bq = BigQueryClient()
    dataset_id = f"{bq.project_id}.{bq.dataset_id}"
    
    # 1. Security Access Log Table
    log_table_id = f"{dataset_id}.security_access_log"
    schema = [
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("action", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("ip_address", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("result", "STRING", mode="NULLABLE"),
    ]
    
    try:
        table = bigquery.Table(log_table_id, schema=schema)
        bq.client.create_table(table, exists_ok=True)
        print(f"Verified Security Access Log table: {log_table_id}")
    except Exception as e:
        print(f"Failed to create log table: {e}")

    # 2. System Freeze Policy (Optional initial state)
    # We don't necessarily want to freeze it now, but ensure policy_registry supports it.
    # The routes handle the insertion of the policy record.

if __name__ == "__main__":
    init_security_layer()
