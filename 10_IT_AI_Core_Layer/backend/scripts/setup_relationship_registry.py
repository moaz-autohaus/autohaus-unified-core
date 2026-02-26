"""
Phase 7 - Setup for `relationship_type_registry`
Creates the relationships schema table and seeds valid edge types.
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

def setup_registry():
    client = get_bq_client()
    if not client:
        print("No BigQuery client available.")
        return

    ddl = """
    CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.relationship_type_registry` (
      relationship_type STRING NOT NULL,
      source_type STRING NOT NULL, -- e.g. DOCUMENT or VEHICLE
      target_type STRING NOT NULL, -- e.g. VEHICLE, PERSON, VENDOR
      description STRING,
      active BOOL DEFAULT TRUE,
      requires_evidence BOOL DEFAULT TRUE
    ) CLUSTER BY source_type, target_type;
    """
    try:
        client.query(ddl).result()
        print("✅ Created relationship_type_registry table")
    except Exception as e:
        print(f"❌ Failed to create table: {e}")

    # Initial valid edges (Document -> Entity)
    edges = [
        ("SUBJECT", "DOCUMENT", "VEHICLE"),
        ("OWNER", "DOCUMENT", "PERSON"),
        ("COUNTERPARTY", "DOCUMENT", "PERSON"),
        ("COUNTERPARTY", "DOCUMENT", "VENDOR"),
        ("SOURCE", "DOCUMENT", "VENDOR"),
        ("INSURED", "DOCUMENT", "PERSON"),
        ("INSURED", "DOCUMENT", "VENDOR"),
        ("REFERENCE", "DOCUMENT", "PERSON"),
        ("REFERENCE", "DOCUMENT", "VENDOR"),
    ]

    print("Seeding valid relationship edges...")
    for rel, src, tgt in edges:
        query = f"""
            SELECT count(*) as cnt 
            FROM `autohaus-infrastructure.autohaus_cil.relationship_type_registry`
            WHERE relationship_type = @rel AND source_type = @src AND target_type = @tgt
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("rel", "STRING", rel),
                bigquery.ScalarQueryParameter("src", "STRING", src),
                bigquery.ScalarQueryParameter("tgt", "STRING", tgt),
            ]
        )
        try:
            res = list(client.query(query, job_config=job_config).result())
            if res[0].cnt == 0:
                insert_query = f"""
                    INSERT INTO `autohaus-infrastructure.autohaus_cil.relationship_type_registry`
                    (relationship_type, source_type, target_type, description)
                    VALUES (@rel, @src, @tgt, 'Seeded default')
                """
                client.query(insert_query, job_config=job_config).result()
                print(f"  + Seeded {src} -[{rel}]-> {tgt}")
            else:
                print(f"  ~ Skipped {src} -[{rel}]-> {tgt} (exists)")
        except Exception as e:
            print(f"  ❌ Error seeding edge: {e}")

if __name__ == "__main__":
    setup_registry()
