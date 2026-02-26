from google.cloud import bigquery
import os
from dotenv import load_dotenv

def setup_views():
    load_dotenv(os.path.expanduser("~/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/auth/.env"))
    
    # We might need explicit impersonation similar to other scripts, 
    # but the machine environment generally has default credentials or service account JSON.
    client = bigquery.Client(project="autohaus-infrastructure")
    
    correction_patterns_query = """
    CREATE OR REPLACE VIEW `autohaus-infrastructure.autohaus_cil.correction_patterns` AS
    SELECT 
        JSON_VALUE(payload, '$.field_name') as field_name,
        JSON_VALUE(payload, '$.system_value') as system_value,
        JSON_VALUE(payload, '$.human_value') as human_value,
        COUNT(*) as correction_count,
        MAX(timestamp) as last_corrected_at
    FROM `autohaus-infrastructure.autohaus_cil.cil_events`
    WHERE event_type = 'CORRECTION_APPLIED'
    GROUP BY 1, 2, 3
    ORDER BY correction_count DESC
    """
    
    entity_trust_summary_query = """
    CREATE OR REPLACE VIEW `autohaus-infrastructure.autohaus_cil.entity_trust_summary` AS
    SELECT
        entity_type,
        entity_id,
        status,
        authority_level,
        completeness_score,
        created_at
    FROM `autohaus-infrastructure.autohaus_cil.entity_registry`
    """
    
    question_debt_summary_query = """
    CREATE OR REPLACE VIEW `autohaus-infrastructure.autohaus_cil.question_debt_summary` AS
    SELECT
        priority,
        status,
        COUNT(*) as count
    FROM `autohaus-infrastructure.autohaus_cil.open_questions`
    GROUP BY 1, 2
    """
    
    print("Creating correction_patterns view...")
    client.query(correction_patterns_query).result()
    print("Creating entity_trust_summary view...")
    client.query(entity_trust_summary_query).result()
    print("Creating question_debt_summary view...")
    client.query(question_debt_summary_query).result()
    
    print("Governance views successfully created.")

if __name__ == "__main__":
    setup_views()
