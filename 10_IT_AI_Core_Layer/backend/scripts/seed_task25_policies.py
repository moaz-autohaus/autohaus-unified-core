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

def seed_task25_policies():
    client = get_bq_client()
    if not client:
        print("No BigQuery client available. Cannot seed.")
        return

    policies = [
        # PIPELINE Domain
        ("PIPELINE", "critical_fields", json.dumps(["ein", "vin", "policy_number", "ownership_pct", "license_number"])),
        ("PIPELINE", "conflict_tolerance_VEHICLE_price", "0.05"),
        ("PIPELINE", "conflict_tolerance_PERSON_email", "0.0"),
        ("PIPELINE", "conflict_tolerance_ENTITY_ein", "0.0"),
        ("PIPELINE", "question_sla_hours_CONFLICT", "24"),
        ("PIPELINE", "question_sla_hours_ASSERTION", "72"),
        ("PIPELINE", "question_sla_hours_IEA", "4"),
        ("PIPELINE", "question_sla_hours_MANUAL", "48"),

        # AGENTS Domain
        ("AGENTS", "attention_sms_threshold", "7"),
        ("AGENTS", "attention_urgency_scale", json.dumps({
            "1-3": "ROUTINE",
            "4-6": "ELEVATED", 
            "7-8": "URGENT",
            "9-10": "CRITICAL"
        })),
        ("AGENTS", "iea_confidence_threshold", "0.7"),
        ("AGENTS", "iea_required_fields_INVENTORY", json.dumps(["vin", "entity"])),
        ("AGENTS", "iea_required_fields_FINANCE", json.dumps(["entity", "time_period"])),
        ("AGENTS", "iea_required_fields_LOGISTICS", json.dumps(["driver_id", "vehicle_id"])),
        ("AGENTS", "iea_required_fields_SERVICE", json.dumps(["vin", "service_type"])),
        ("AGENTS", "iea_required_fields_CRM", json.dumps(["contact_identifier"])),
        ("AGENTS", "iea_required_fields_COMPLIANCE", json.dumps(["entity", "document_type"]))
    ]

    print("Seeding Task 2.5 policies...")
    for domain, key, value in policies:
        query = f"""
            SELECT count(*) as cnt 
            FROM `autohaus-infrastructure.autohaus_cil.policy_registry`
            WHERE domain = @domain AND key = @key 
            AND applies_to_entity IS NULL
            AND applies_to_doc_type IS NULL
            AND applies_to_entity_type IS NULL
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("domain", "STRING", domain),
                bigquery.ScalarQueryParameter("key", "STRING", key)
            ]
        )
        try:
            res = list(client.query(query, job_config=job_config).result())
            if res[0].cnt == 0:
                insert_query = f"""
                    INSERT INTO `autohaus-infrastructure.autohaus_cil.policy_registry`
                    (domain, key, value)
                    VALUES (@domain, @key, @value)
                """
                insert_config = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter("domain", "STRING", domain),
                        bigquery.ScalarQueryParameter("key", "STRING", key),
                        bigquery.ScalarQueryParameter("value", "STRING", value)
                    ]
                )
                client.query(insert_query, job_config=insert_config).result()
                print(f"  + Seeded {domain}.{key} = {value}")
            else:
                print(f"  ~ Skipped {domain}.{key} (already exists)")
        except Exception as e:
            print(f"  ❌ Error seeding {domain}.{key}: {e}")
            
    print("Done seeding.")

if __name__ == "__main__":
    seed_task25_policies()
