import os
import uuid
import json
from datetime import datetime, timezone

from google.cloud import bigquery

# Import the BQ client wrapper
from database.bigquery_client import BigQueryClient

def print_results(client):
    print("--- 1. Personnel (master_person_graph) ---")
    query = "SELECT master_person_id, first_name, entity_tags FROM `autohaus-infrastructure.autohaus_cil.master_person_graph` LIMIT 10"
    try:
        rows = client.query(query).result()
        for r in rows:
            print(f"- {r.first_name} ({r.master_person_id}): tags={r.entity_tags}")
    except Exception as e:
        print("Error:", e)

    print("\n--- 2. Open Questions ---")
    query = "SELECT question_id, priority, status FROM `autohaus-infrastructure.autohaus_cil.open_questions` ORDER BY priority"
    try:
        rows = list(client.query(query).result())
        print(f"Total Canonical Questions: {len(rows)}")
        high_count = sum(1 for r in rows if r.priority == "HIGH")
        med_count = sum(1 for r in rows if r.priority == "MEDIUM")
        print(f"HIGH items: {high_count}, MEDIUM items: {med_count}")
    except Exception as e:
        print("Error:", e)
        
    print("\n--- 3. Policy Registry ---")
    query = "SELECT domain, key as policy_key, value as policy_value FROM `autohaus-infrastructure.autohaus_cil.policy_registry` WHERE domain IN ('PIPELINE', 'COMPLIANCE')"
    try:
        rows = client.query(query).result()
        for r in rows:
            print(f"[{r.domain}] {r.policy_key} = {r.policy_value}")
    except Exception as e:
        print("Error:", e)

    print("\n--- 4. Event Spine Baseline ---")
    query = "SELECT event_type, actor_id, actor_role FROM `autohaus-infrastructure.autohaus_cil.cil_events` WHERE event_type = 'SYSTEM_INITIALIZED' LIMIT 1"
    try:
        rows = list(client.query(query).result())
        for r in rows:
            print(f"- Found Event: {r.event_type} | Actor: {r.actor_id} | Authority: {r.actor_role}")
    except Exception as e:
        print("Error:", e)

    print("\n--- 5. Hitl Events Rejection ---")
    query = "SELECT hitl_event_id as event_id, status FROM `autohaus-infrastructure.autohaus_cil.hitl_events` WHERE hitl_event_id = '37ab9b3e-09ae-47b4-851d-2f1bde056a07'"
    try:
        rows = list(client.query(query).result())
        if not rows:
            print("Proposal not found.")
        for r in rows:
            print(f"- Proposal {r.event_id} status is: {r.status}")
    except Exception as e:
        print("Error:", e)

# Use standard SQL deletes for cleanup
def cleanup_tables(client):
    try:
        client.query("DELETE FROM `autohaus-infrastructure.autohaus_cil.master_person_graph` WHERE true").result()
        client.query("DELETE FROM `autohaus-infrastructure.autohaus_cil.open_questions` WHERE true").result()
        client.query("DELETE FROM `autohaus-infrastructure.autohaus_cil.policy_registry` WHERE true").result()
        client.query("DELETE FROM `autohaus-infrastructure.autohaus_cil.cil_events` WHERE event_type = 'SYSTEM_INITIALIZED'").result()
    except Exception as e:
        print("Cleanup failed:", e)

def seed():
    bq = BigQueryClient()
    client = bq.client

    timestamp = datetime.utcnow().isoformat() + "Z"
    
    cleanup_tables(client)

    # 1. Seed master_person_graph
    personnel = [
        {"master_person_id": "P_MOAZ", "first_name": "Moaz", "last_name": "Sial", "entity_tags": "[\"SOVEREIGN\", \"VERIFIED\"]", "created_at": timestamp},
        {"master_person_id": "P_KAMRAN", "first_name": "Kamran", "last_name": "Unknown", "entity_tags": "[\"STANDARD\", \"VERIFIED\"]", "created_at": timestamp},
        {"master_person_id": "P_AHSIN", "first_name": "Ahsin", "last_name": "Unknown", "entity_tags": "[\"SOVEREIGN\", \"VERIFIED\"]", "created_at": timestamp},
        {"master_person_id": "P_ASIM", "first_name": "Asim", "last_name": "Unknown", "entity_tags": "[\"STANDARD\", \"STUB_PENDING_CONTACT\"]", "created_at": timestamp},
        {"master_person_id": "P_MOHSIN", "first_name": "Mohsin", "last_name": "Unknown", "entity_tags": "[\"STANDARD\", \"STUB_PENDING_CONTACT\"]", "created_at": timestamp},
        {"master_person_id": "P_SUNNY", "first_name": "Sunny", "last_name": "Unknown", "entity_tags": "[\"FIELD\", \"VERIFIED\"]", "created_at": timestamp},
    ]

    job_config_append = bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_APPEND)
    try:
        client.load_table_from_json(personnel, "autohaus-infrastructure.autohaus_cil.master_person_graph", job_config=job_config_append).result()
    except Exception as e:
        print("Could not seed personnel:", e)

    # 2. Seed open questions (9 canonical questions)
    q_sql = f"""
    INSERT INTO `autohaus-infrastructure.autohaus_cil.open_questions`
    (question_id, question_type, description, priority, status, created_at)
    VALUES
    ('Q1', 'INITIAL_CONTEXT', 'Policy 66465558 vs KammLLCTPP-6041894 — same or separate instrument?', 'HIGH', 'OPEN', CURRENT_TIMESTAMP()),
    ('Q2', 'INITIAL_CONTEXT', 'Grinnell Mutual — dual coverage or replaced by Auto-Owners?', 'HIGH', 'OPEN', CURRENT_TIMESTAMP()),
    ('Q4', 'INITIAL_CONTEXT', 'AstroLogistics EIN', 'MEDIUM', 'OPEN', CURRENT_TIMESTAMP()),
    ('Q5', 'INITIAL_CONTEXT', 'Asim email and phone', 'MEDIUM', 'OPEN', CURRENT_TIMESTAMP()),
    ('Q6', 'INITIAL_CONTEXT', 'Mohsin email and phone', 'MEDIUM', 'OPEN', CURRENT_TIMESTAMP()),
    ('Q7', 'INITIAL_CONTEXT', 'VINs for 11 stub vehicles', 'HIGH', 'OPEN', CURRENT_TIMESTAMP()),
    ('Q8', 'INITIAL_CONTEXT', 'Workers Comp and EPLI details for Carbon LLC', 'MEDIUM', 'OPEN', CURRENT_TIMESTAMP()),
    ('Q9', 'INITIAL_CONTEXT', 'Fleet and Logistics policy details for Fluiditruck and Carlux', 'MEDIUM', 'OPEN', CURRENT_TIMESTAMP()),
    ('Q10', 'INITIAL_CONTEXT', 'Any other critical missing context', 'HIGH', 'OPEN', CURRENT_TIMESTAMP())
    """
    try:
        client.query(q_sql).result()
    except Exception as e:
        print("Could not seed questions:", e)

    # 3. Seed policy registry
    p_sql = f"""
    INSERT INTO `autohaus-infrastructure.autohaus_cil.policy_registry`
    (domain, key, value, created_at)
    VALUES
    ('PIPELINE', 'extraction_temperature', '0.0', CURRENT_TIMESTAMP()),
    ('COMPLIANCE', 'inventory_max_units', '15', CURRENT_TIMESTAMP()),
    ('COMPLIANCE', 'insurance_exposure_ceiling', '200000', CURRENT_TIMESTAMP()),
    ('COMPLIANCE', 'iowa_title_deadline_days', '30', CURRENT_TIMESTAMP()),
    ('COMPLIANCE', 'iowa_title_warning_days', '7', CURRENT_TIMESTAMP()),
    ('COMPLIANCE', 'inventory_warning_units', '13', CURRENT_TIMESTAMP()),
    ('COMPLIANCE', 'insurance_alert_threshold_80pct', '160000', CURRENT_TIMESTAMP()),
    ('COMPLIANCE', 'cit_aging_threshold_days', '5', CURRENT_TIMESTAMP()),
    ('HITL', 'ROLE_PERMISSIONS', '{{"SOVEREIGN": ["*"], "STANDARD": ["MEDIA_INGEST", "OVERRIDE_FIELDS", "VIEW_CLAIMS", "VIEW_QUESTIONS"], "FIELD": ["MEDIA_INGEST", "ASSERT_ENTITY", "VIEW_QUESTIONS"]}}', CURRENT_TIMESTAMP())
    """
    try:
        client.query(p_sql).result()
    except Exception as e:
        print("Could not seed policies:", e)

    # 4. Seed event spine baseline (SYSTEM_INITIALIZED)
    e_sql = f"""
    INSERT INTO `autohaus-infrastructure.autohaus_cil.cil_events`
    (event_id, event_type, target_id, target_type, actor_id, actor_role, actor_type, payload, created_at, timestamp)
    VALUES
    ('{str(uuid.uuid4())}', 'SYSTEM_INITIALIZED', 'SYSTEM', 'SYSTEM', 'MOAZ_SIAL', 'SOVEREIGN', 'SYSTEM', JSON '{{}}', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP())
    """
    try:
        client.query(e_sql).result()
    except Exception as e:
        print("Could not seed events:", e)

    # 5. Stale proposal rejection
    update_hitl = "UPDATE `autohaus-infrastructure.autohaus_cil.hitl_events` SET status = 'REJECTED' WHERE hitl_event_id = '37ab9b3e-09ae-47b4-851d-2f1bde056a07'"
    try:
        client.query(update_hitl).result()
    except Exception as e:
        print("Could not update HITL event:", e)

    # Print results
    print_results(client)



if __name__ == "__main__":
    try:
        seed()
    except Exception as e:
        print(f"Failed to run seed script: {e}")
        print("\nPlease run `gcloud auth application-default login` if you see a reauth error.")
