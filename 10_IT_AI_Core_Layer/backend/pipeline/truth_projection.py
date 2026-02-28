"""
AutoHaus CIL — Native Governance Truth Projection (Pass 7)
"""

import json
import logging
from typing import Dict, Any, List
from datetime import datetime

from database.policy_engine import get_policy
from database.open_questions import raise_open_question

logger = logging.getLogger("autohaus.truth_projection")

def project_entity_fact(bq_client, entity_id: str, entity_type: str, field_name: str, new_value: str, base_confidence: float, source_doc_id: str, source_doc_type: str):
    """
    Project a new claim into `entity_facts`, applying survivorship rules
    and conflict resolution.
    """
    if not new_value:
        return

    # 0. Global Compliance Freeze Check
    from database.policy_engine import get_policy
    if get_policy("SYSTEM", "FROZEN"):
        logger.warning(f"[SECURITY] Truth projection blocked: System is FROZEN.")
        return

    # 1. Fetch current active facts for this field
    query = """
        SELECT value, confidence_score, source_type, status 
        FROM `autohaus-infrastructure.autohaus_cil.entity_facts`
        WHERE entity_id = @eid AND field_name = @fn AND status IN ('ACTIVE', 'CONFLICTING_CLAIM')
    """
    from google.cloud import bigquery as bq
    job_config = bq.QueryJobConfig(
        query_parameters=[
            bq.ScalarQueryParameter("eid", "STRING", entity_id),
            bq.ScalarQueryParameter("fn", "STRING", field_name),
        ]
    )
    try:
        active_claims = list(bq_client.client.query(query, job_config=job_config).result())
    except Exception as e:
        logger.error(f"[TRUTH] Failed to fetch facts: {e}")
        return

    # Base formula for confidence
    # To simplify, we'll use base_confidence for now.
    final_confidence = base_confidence

    if not active_claims:
        # No conflict, insert as ACTIVE
        _insert_fact(bq_client, entity_id, entity_type, field_name, new_value, final_confidence, source_doc_id, source_doc_type, "ACTIVE")
        return

    # We have existing claims. Are they identical?
    # If the value matches an existing active claim, we don't need a new fact row, or we can just append as RESOLVED.
    matching_claim = next((c for c in active_claims if str(c.value).lower() == str(new_value).lower()), None)
    if matching_claim:
        # It's corroboration. Just insert as RESOLVED to keep lineage without conflict.
        _insert_fact(bq_client, entity_id, entity_type, field_name, new_value, final_confidence, source_doc_id, source_doc_type, "RESOLVED")
        return

    # Conflict! Apply Survivorship Policy
    survivorship_json = get_policy("SURVIVORSHIP", "field_authority_hierarchy") or '[]'
    try:
        hierarchy = json.loads(survivorship_json) if isinstance(survivorship_json, str) else survivorship_json
    except:
        hierarchy = []

    # Helper to rank doc_types
    def get_rank(doc_type: str) -> int:
        try:
            return hierarchy.index(doc_type)
        except ValueError:
            return -1

    new_rank = get_rank(source_doc_type)
    
    conflict_resolved = True
    for old_claim in active_claims:
        old_rank = get_rank(old_claim.source_type)
        
        if new_rank > old_rank:
            # New is better. Retire old.
            _retire_fact(bq_client, entity_id, field_name, old_claim.source_type)
        elif old_rank > new_rank:
            # Old is better. New is immediately resolved/rejected.
            _insert_fact(bq_client, entity_id, entity_type, field_name, new_value, final_confidence, source_doc_id, source_doc_type, "RESOLVED")
            return
        else:
            # Tied rank! Unresolvable conflict.
            conflict_resolved = False

    if conflict_resolved:
        # We beat all existing non-matching claims
        _insert_fact(bq_client, entity_id, entity_type, field_name, new_value, final_confidence, source_doc_id, source_doc_type, "ACTIVE")
    else:
        # Unresolvable conflict. Mark all as CONFLICTING_CLAIM and raise question.
        _mark_conflicts(bq_client, entity_id, field_name)
        _insert_fact(bq_client, entity_id, entity_type, field_name, new_value, final_confidence, source_doc_id, source_doc_type, "CONFLICTING_CLAIM")
        
        raise_open_question(
            bq_client,
            question_type="CONFLICTING_CLAIM",
            priority="HIGH",
            context={"entity_id": entity_id, "field_name": field_name, "new_value": new_value, "source_doc_type": source_doc_type},
            description=f"Conflicting claims for {field_name} on {entity_type} {entity_id}. Could not auto-resolve between {source_doc_type} and existing claims."
        )


def _insert_fact(bq_client, eid, etype, fname, val, conf, sid, stype, status):
    now = datetime.utcnow().isoformat()
    row = {
        "entity_id": eid,
        "entity_type": etype,
        "field_name": fname,
        "value": str(val),
        "confidence_score": float(conf),
        "source_document_id": sid,
        "source_type": stype,
        "status": status,
        "created_at": now,
        "updated_at": now
    }
    bq_client.insert_rows_json("autohaus-infrastructure.autohaus_cil.entity_facts", [row])

def _retire_fact(bq_client, eid, fname, stype):
    now = datetime.utcnow().isoformat()
    query = "UPDATE `autohaus-infrastructure.autohaus_cil.entity_facts` SET status = 'RESOLVED', updated_at = @now WHERE entity_id = @eid AND field_name = @fname AND source_type = @stype"
    from google.cloud import bigquery as bq
    job_config = bq.QueryJobConfig(query_parameters=[
        bq.ScalarQueryParameter("now", "STRING", now),
        bq.ScalarQueryParameter("eid", "STRING", eid),
        bq.ScalarQueryParameter("fname", "STRING", fname),
        bq.ScalarQueryParameter("stype", "STRING", stype),
    ])
    bq_client.client.query(query, job_config=job_config).result()

def _mark_conflicts(bq_client, eid, fname):
    now = datetime.utcnow().isoformat()
    query = "UPDATE `autohaus-infrastructure.autohaus_cil.entity_facts` SET status = 'CONFLICTING_CLAIM', updated_at = @now WHERE entity_id = @eid AND field_name = @fname AND status = 'ACTIVE'"
    from google.cloud import bigquery as bq
    job_config = bq.QueryJobConfig(query_parameters=[
        bq.ScalarQueryParameter("now", "STRING", now),
        bq.ScalarQueryParameter("eid", "STRING", eid),
        bq.ScalarQueryParameter("fname", "STRING", fname),
    ])
    bq_client.client.query(query, job_config=job_config).result()

def rebuild_entity_facts(bq_client, entity_id: str):
    """
    Rebuild the truth projection for a given entity_id.
    Synchronizes facts with master tables and emits TRUTH_PROJECTION_REBUILT event.
    """
    import uuid
    now = datetime.utcnow().isoformat()
    logger.info(f"[TRUTH] Rebuilding entity facts for {entity_id}")
    
    event_row = {
        "event_id": str(uuid.uuid4()),
        "event_type": "TRUTH_PROJECTION_REBUILT",
        "timestamp": now,
        "actor_type": "SYSTEM",
        "actor_id": "truth_projection",
        "actor_role": "SYSTEM",
        "target_type": "ENTITY",
        "target_id": entity_id,
        "payload": json.dumps({"action": "rebuild_entity_facts"}),
        "metadata": None,
        "idempotency_key": f"rebuild_{entity_id}_{int(datetime.utcnow().timestamp())}",
    }
    
    try:
        bq_client.insert_rows_json(
            "autohaus-infrastructure.autohaus_cil.cil_events", [event_row]
        )
    except Exception as e:
        logger.error(f"[TRUTH] Failed to log rebuild event: {e}")
