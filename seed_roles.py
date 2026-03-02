import os
import json
import logging
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)

def seed_role_permissions():
    client = bigquery.Client()
    table_id = "autohaus-infrastructure.autohaus_cil.policy_registry"
    
    row = {
        "domain": "HITL",
        "key": "ROLE_PERMISSIONS",
        "value": json.dumps({"SOVEREIGN": ["*"], "STANDARD": ["read_only"], "FIELD": ["read_only"]}),
        "description": "Role permissions for open questions"
    }
    
    q = f"""
    MERGE `{table_id}` T
    USING (SELECT 'HITL' as domain, 'ROLE_PERMISSIONS' as key) S
    ON T.domain = S.domain AND T.key = S.key
    WHEN MATCHED THEN
      UPDATE SET value = @val, description = @desc
    WHEN NOT MATCHED THEN
      INSERT (domain, key, value, version, is_active, last_updated_by, description)
      VALUES ('HITL', 'ROLE_PERMISSIONS', @val, 1, True, 'system_seeder', @desc)
    """
    jc = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("val", "STRING", row["value"]),
            bigquery.ScalarQueryParameter("desc", "STRING", row["description"])
        ]
    )
    client.query(q, job_config=jc).result()
    print("Seeded HITL.ROLE_PERMISSIONS in BigQuery successfully.")

if __name__ == "__main__":
    seed_role_permissions()
