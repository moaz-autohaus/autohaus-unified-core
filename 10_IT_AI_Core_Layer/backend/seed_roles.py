import json
from google.cloud import bigquery

def seed_role_permissions():
    client = bigquery.Client()
    table_id = "autohaus-infrastructure.autohaus_cil.policy_registry"
    
    val = json.dumps({"SOVEREIGN": ["*"], "STANDARD": ["read_only"], "FIELD": ["read_only"]})
    q = f"""
    MERGE `{table_id}` T USING (SELECT 'HITL' as domain, 'ROLE_PERMISSIONS' as key) S
    ON T.domain = S.domain AND T.key = S.key
    WHEN NOT MATCHED THEN INSERT (domain, key, value, version, is_active, last_updated_by, description)
    VALUES ('HITL', 'ROLE_PERMISSIONS', @val, 1, True, 'system_seeder', 'Role permissions')
    """
    jc = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("val", "STRING", val)])
    client.query(q, job_config=jc).result()
    print("Seeded HITL.ROLE_PERMISSIONS successfully.")

if __name__ == "__main__":
    seed_role_permissions()
