
import json
import uuid
from datetime import datetime, timezone
from google.cloud import bigquery
from database.bigquery_client import BigQueryClient

def update_role_permissions():
    bq = BigQueryClient()
    
    new_permissions = {
        "SOVEREIGN": [
            "CONTEXT_ADD",
            "FIELD_OVERRIDE",
            "ENTITY_MERGE",
            "ENTITY_SPLIT",
            "REPROCESS",
            "CONFIRM_CLASSIFICATION",
            "ROLLBACK",
            "POLICY_CHANGE",
            "MEDIA_INGEST",
            "FINANCIAL_JOURNAL_PROPOSAL",
            "GMAIL_DRAFT_PROPOSAL",
            "ENTITY_MODIFICATION"
        ],
        "SYSTEM": [
            "CONTEXT_ADD",
            "FIELD_OVERRIDE",
            "ENTITY_MERGE",
            "ENTITY_SPLIT",
            "REPROCESS",
            "CONFIRM_CLASSIFICATION",
            "ROLLBACK",
            "POLICY_CHANGE",
            "MEDIA_INGEST",
            "FINANCIAL_JOURNAL_PROPOSAL",
            "GMAIL_DRAFT_PROPOSAL",
            "ENTITY_MODIFICATION"
        ],
        "STANDARD": [
            "CONTEXT_ADD",
            "FIELD_OVERRIDE",
            "CONFIRM_CLASSIFICATION",
            "MEDIA_INGEST",
            "FINANCIAL_JOURNAL_PROPOSAL",
            "GMAIL_DRAFT_PROPOSAL",
            "ENTITY_MODIFICATION"
        ],
        "FIELD": [
            "CONTEXT_ADD",
            "MEDIA_INGEST"
        ]
    }
    
    # Update active status for old policy
    deactivate_query = f"""
        UPDATE `{bq.project_id}.{bq.dataset_id}.policy_registry`
        SET active = FALSE
        WHERE domain = 'HITL' AND key = 'ROLE_PERMISSIONS' AND active = TRUE
    """
    bq.client.query(deactivate_query).result()
    
    # Insert new version
    row = {
        "domain": "HITL",
        "key": "ROLE_PERMISSIONS",
        "value": json.dumps(new_permissions),
        "applies_to_entity": None,
        "applies_to_doc_type": None,
        "applies_to_entity_type": None,
        "version": 2,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "SYSTEM",
        "active": True
    }
    
    errors = bq.client.insert_rows_json(f"{bq.project_id}.{bq.dataset_id}.policy_registry", [row])
    if errors:
        print(f"FAILED to update permissions: {errors}")
    else:
        print("✅ HITL Role Permissions updated successfully.")

if __name__ == "__main__":
    update_role_permissions()
