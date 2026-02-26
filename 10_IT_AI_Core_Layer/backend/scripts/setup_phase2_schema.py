"""
Schema setup for Phase 2 — Master Entity tables + Pass 5 tables.
Run once to create all Phase 2 BigQuery tables.
"""
import os, json
from google.cloud import bigquery
from google.oauth2 import service_account

def get_bq_client():
    project_id = "autohaus-infrastructure"
    key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "auth", "replit-sa-key.json")
    if os.path.exists(key_path):
        credentials = service_account.Credentials.from_service_account_file(key_path)
        return bigquery.Client(credentials=credentials, project=project_id)
    sa_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    if sa_json:
        credentials = service_account.Credentials.from_service_account_info(json.loads(sa_json))
        return bigquery.Client(credentials=credentials, project=project_id)
    return None

def execute_ddl():
    client = get_bq_client()
    if not client:
        print("No BQ client. Aborting.")
        return

    ddls = [
        # ── Master Entity Tables (Step 5) ──
        """
        CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.vehicles` (
          vehicle_id STRING NOT NULL,
          vin STRING NOT NULL,
          year INT64,
          make STRING,
          model STRING,
          trim STRING,
          color STRING,
          authority_level STRING DEFAULT 'ADVISORY',
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.persons` (
          person_id STRING NOT NULL,
          canonical_name STRING,
          phone STRING,
          email STRING,
          authority_level STRING DEFAULT 'ADVISORY',
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.vendors` (
          vendor_id STRING NOT NULL,
          canonical_name STRING NOT NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.vendor_aliases` (
          alias_id STRING NOT NULL,
          raw_name STRING NOT NULL,
          canonical_vendor_id STRING NOT NULL,
          canonical_name STRING NOT NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
          created_by STRING
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.transactions` (
          transaction_id STRING NOT NULL,
          vin STRING,
          vendor_id STRING,
          person_id STRING,
          amount FLOAT64,
          transaction_type STRING,
          transaction_date DATE,
          document_id STRING,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.jobs` (
          job_id STRING NOT NULL,
          vin STRING,
          service_entity STRING,
          ro_number STRING,
          total_cost FLOAT64,
          job_date DATE,
          closed BOOL DEFAULT FALSE,
          document_id STRING,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
        );
        """,
        # ── Pass 5 Knowledge Tables (Steps 6-7) ──
        """
        CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.schema_registry` (
          schema_id STRING NOT NULL,
          schema_version STRING NOT NULL,
          yaml_content STRING,
          field_mapping JSON,
          migration_policy STRING,
          active BOOL DEFAULT TRUE,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.extraction_fields` (
          field_id STRING NOT NULL,
          document_id STRING NOT NULL,
          extraction_version_id STRING NOT NULL,
          schema_id STRING,
          field_name STRING NOT NULL,
          field_value STRING,
          field_type STRING,
          extraction_confidence FLOAT64,
          authority_level STRING DEFAULT 'ADVISORY',
          source_location STRING,
          requires_review BOOL DEFAULT FALSE,
          active_override_id STRING,
          effective_value STRING,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.document_entity_links` (
          link_id STRING NOT NULL,
          document_id STRING NOT NULL,
          entity_type STRING NOT NULL,
          entity_id STRING NOT NULL,
          relationship_type STRING NOT NULL,
          resolution_method STRING,
          resolution_confidence FLOAT64,
          active BOOL DEFAULT TRUE,
          superseded_by_link_id STRING,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
          created_by_event_id STRING
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.open_questions` (
          question_id STRING NOT NULL,
          document_id STRING,
          entity_type STRING,
          entity_id STRING,
          question_type STRING NOT NULL,
          question_text STRING NOT NULL,
          context JSON,
          assigned_to STRING,
          assigned_role STRING,
          due_by TIMESTAMP,
          escalation_target STRING,
          status STRING DEFAULT 'OPEN',
          resolution JSON,
          resolved_at TIMESTAMP,
          resolved_by STRING,
          resolution_event_id STRING,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
        );
        """,
        # ── Pass 6 HITL Tables (Step 8) ──
        """
        CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.hitl_events` (
          hitl_event_id STRING NOT NULL,
          timestamp TIMESTAMP NOT NULL,
          actor_user_id STRING NOT NULL,
          actor_role STRING NOT NULL,
          source STRING NOT NULL,
          target_type STRING NOT NULL,
          target_id STRING NOT NULL,
          action_type STRING NOT NULL,
          status STRING DEFAULT 'PROPOSED',
          payload JSON NOT NULL,
          diff JSON,
          reason STRING,
          intent_confidence FLOAT64,
          proposal_expires_at TIMESTAMP,
          validated_at TIMESTAMP,
          validation_result JSON,
          applied_at TIMESTAMP,
          applied_by STRING,
          rolled_back_at TIMESTAMP,
          rollback_event_id STRING,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
        ) PARTITION BY DATE(timestamp) CLUSTER BY action_type, status;
        """,
        """
        CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.field_overrides` (
          override_id STRING NOT NULL,
          document_id STRING NOT NULL,
          extraction_version_id STRING NOT NULL,
          field_name STRING NOT NULL,
          original_value STRING,
          override_value STRING NOT NULL,
          authority_level STRING DEFAULT 'ASSERTED',
          active BOOL DEFAULT TRUE,
          effective_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
          effective_to TIMESTAMP,
          hitl_event_id STRING NOT NULL,
          applied_by STRING NOT NULL,
          notes STRING,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.entity_resolution_actions` (
          action_id STRING NOT NULL,
          entity_type STRING NOT NULL,
          source_entity_id STRING NOT NULL,
          target_entity_id STRING,
          resolution_type STRING NOT NULL,
          confidence FLOAT64 DEFAULT 1.0,
          raw_name STRING,
          canonical_name STRING,
          hitl_event_id STRING NOT NULL,
          applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
          applied_by STRING NOT NULL,
          affected_document_count INT64,
          link_reassignment_complete BOOL DEFAULT FALSE,
          drift_sweep_completed BOOL DEFAULT FALSE,
          drift_sweep_completed_at TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.drift_sweep_results` (
          sweep_id STRING NOT NULL,
          sweep_type STRING NOT NULL,
          target_type STRING,
          target_id STRING,
          finding STRING NOT NULL,
          severity STRING NOT NULL,
          auto_correctable BOOL DEFAULT FALSE,
          auto_corrected BOOL DEFAULT FALSE,
          auto_correction_detail STRING,
          escalated BOOL DEFAULT FALSE,
          escalated_to STRING,
          resolved BOOL DEFAULT FALSE,
          resolved_at TIMESTAMP,
          resolution_event_id STRING,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
        );
        """,
    ]

    success = 0
    failed = 0
    for ddl in ddls:
        parts = ddl.split("`")
        table_name = parts[3].split(".")[-1] if len(parts) > 3 else "unknown"
        try:
            job = client.query(ddl)
            job.result()
            print(f"  ✅ {table_name}")
            success += 1
        except Exception as e:
            print(f"  ❌ {table_name}: {e}")
            failed += 1

    print(f"\nDone: {success} created, {failed} failed.")

if __name__ == "__main__":
    execute_ddl()
