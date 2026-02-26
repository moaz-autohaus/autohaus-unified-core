"""
Phase 7 - Setup for `policy_registry`
Creates the table and seeds initial constants into governed rules.
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
    CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.policy_registry` (
      domain STRING NOT NULL,
      key STRING NOT NULL,
      value STRING NOT NULL,
      applies_to_entity STRING,
      applies_to_doc_type STRING,
      applies_to_entity_type STRING,
      version INT64 DEFAULT 1,
      active BOOL DEFAULT TRUE,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
      created_by STRING DEFAULT 'SYSTEM'
    ) CLUSTER BY domain, key;
    """
    try:
        client.query(ddl).result()
        print("✅ Created policy_registry table")
    except Exception as e:
        print(f"❌ Failed to create table: {e}")

    # Initial Policies to Seed
    policies = [
        # KAMM Review Requirements
        ("COMPLIANCE", "kamm_review_required", "true", None, "VEHICLE_TITLE", None),
        ("COMPLIANCE", "kamm_review_required", "true", None, "DAMAGE_DISCLOSURE_IA", None),
        
        # Confidence Thresholds
        ("EXTRACTION", "min_confidence_threshold", "0.85", None, None, None), # global default
        ("EXTRACTION", "min_confidence_threshold", "0.95", None, "VEHICLE_TITLE", None), # stricter for title
        ("EXTRACTION", "min_confidence_threshold", "0.80", None, "AUCTION_RECEIPT", None),
        
        # Escalation Rules
        ("ESCALATION", "snooze_duration_hours", "24", None, None, None),
        ("ESCALATION", "max_overdue_hours", "48", None, None, None),
        ("ESCALATION", "breach_action", '"TWILIO_SMS"', None, None, None),
        
        # Seeding Limits
        ("SEEDING", "batch_size", "10", None, None, None),
        ("SEEDING", "pause_sec", "30", None, None, None),
        ("SEEDING", "abort_threshold_usd", "50.00", None, None, None),
        
        # Anomaly / Margin
        ("ANOMALY", "golden_rule_minutes", "60", None, None, None),
        ("ANOMALY", "transport_cost_ceiling", "500.00", None, None, None),
        
        # Survivorship Hierarchies (Field Authority)
        # Format: array of source types in increasing order of trust
        ("SURVIVORSHIP", "field_authority_hierarchy", 
         '["BILL_OF_SALE", "SERVICE_RO", "INSURANCE_CERT", "TRANSPORT_INVOICE", "AUCTION_RECEIPT", "VEHICLE_TITLE"]', 
         None, None, None),
         
        # Authority Levels Enum
        ("CORE", "authority_levels",
         '["STUB", "ADVISORY", "ASSERTED", "VERIFIED", "COMPLIANCE_VERIFIED", "LOCKED", "SOVEREIGN"]',
         None, None, None),
         
        # Drift / Run Frequency
        ("OPS", "drift_sweep_cron_minutes", "15", None, None, None),
    ]

    print("Seeding initial policies...")
    for domain, key, value, entity, doc, ent_type in policies:
        # Check if exists
        query = f"""
            SELECT count(*) as cnt 
            FROM `autohaus-infrastructure.autohaus_cil.policy_registry`
            WHERE domain = @domain AND key = @key 
            AND IFNULL(applies_to_entity, '') = IFNULL(@entity, '')
            AND IFNULL(applies_to_doc_type, '') = IFNULL(@doc, '')
            AND IFNULL(applies_to_entity_type, '') = IFNULL(@ent_type, '')
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("domain", "STRING", domain),
                bigquery.ScalarQueryParameter("key", "STRING", key),
                bigquery.ScalarQueryParameter("entity", "STRING", entity),
                bigquery.ScalarQueryParameter("doc", "STRING", doc),
                bigquery.ScalarQueryParameter("ent_type", "STRING", ent_type),
                bigquery.ScalarQueryParameter("value", "STRING", value),
            ]
        )
        try:
            res = list(client.query(query, job_config=job_config).result())
            if res[0].cnt == 0:
                insert_query = f"""
                    INSERT INTO `autohaus-infrastructure.autohaus_cil.policy_registry`
                    (domain, key, value, applies_to_entity, applies_to_doc_type, applies_to_entity_type)
                    VALUES (@domain, @key, @value, @entity, @doc, @ent_type)
                """
                client.query(insert_query, job_config=job_config).result()
                print(f"  + Seeded {domain}.{key} = {value}")
            else:
                print(f"  ~ Skipped {domain}.{key} (already exists)")
        except Exception as e:
            print(f"  ❌ Error seeding {domain}.{key}: {e}")

if __name__ == "__main__":
    setup_registry()
