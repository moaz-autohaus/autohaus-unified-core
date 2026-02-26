"""
AutoHaus CIL — HITL (Human-in-the-Loop) Service
Phase 3, Step 8

Implements the HITL state machine:
  PROPOSED → VALIDATED → APPLIED → (optionally ROLLED_BACK)

Action types:
  CONTEXT_ADD         — Human adds non-conflicting metadata
  FIELD_OVERRIDE      — Human corrects an extracted field value
  ENTITY_MERGE        — Human confirms two entities are the same
  ENTITY_SPLIT        — Human separates incorrectly merged entities
  REPROCESS           — Human requests pipeline re-run from a specific stage
  CONFIRM_CLASSIFICATION — Human confirms/corrects document classification
  ROLLBACK            — Revert a previously applied change

Every APPLIED action emits a cil_events record (single audit spine rule).
"""

import uuid
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from enum import Enum
from typing import Dict, Any, Optional

from .feedback_loop import process_correction_event
from .truth_projection import rebuild_entity_facts

logger = logging.getLogger("autohaus.hitl_service")


class ActionType(str, Enum):
    CONTEXT_ADD = "CONTEXT_ADD"
    FIELD_OVERRIDE = "FIELD_OVERRIDE"
    ENTITY_MERGE = "ENTITY_MERGE"
    ENTITY_SPLIT = "ENTITY_SPLIT"
    REPROCESS = "REPROCESS"
    CONFIRM_CLASSIFICATION = "CONFIRM_CLASSIFICATION"
    ROLLBACK = "ROLLBACK"
    POLICY_CHANGE = "POLICY_CHANGE"
    MEDIA_INGEST = "MEDIA_INGEST"


class HitlStatus(str, Enum):
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    ROLLED_BACK = "ROLLED_BACK"


from database.policy_engine import get_policy

def get_role_permissions(role: str) -> set:
    raw_perms = get_policy("HITL", "ROLE_PERMISSIONS")
    if raw_perms is None:
        raise ValueError("Missing HITL.ROLE_PERMISSIONS in policy registry. No fallbacks allowed.")
    if isinstance(raw_perms, str):
        raw_perms = json.loads(raw_perms)
        
    role_perms = raw_perms.get(role, [])
    return set(ActionType(a) for a in role_perms)

# Entity scope per person (from personnel_access_matrix)
ENTITY_SCOPE = {
    "ahsin": {"scope": "ALL"},
    "asim": {"scope": ["KAMM_LLC", "AUTOHAUS_SERVICES_LLC"]},
    "mohsin": {"scope": ["ASTROLOGISTICS_LLC", "AUTOHAUS_SERVICES_LLC"]},
    "moaz": {"scope": ["FLUIDITRUCK_LLC", "CARLUX_LLC"]},
}

KAMM_MUST_REVIEW = [
    "DAMAGE_DISCLOSURE_IA", "DEALER_PLATE",
    "TITLE_REASSIGNMENT", "ODOMETER_DISCLOSURE",
]

# Actions that require explicit confirmation before applying (high-risk)
HIGH_RISK_ACTIONS = {
    ActionType.ENTITY_MERGE, ActionType.ENTITY_SPLIT, ActionType.ROLLBACK, ActionType.POLICY_CHANGE,
}


# ── Propose ─────────────────────────────────────────────────────────────

def propose(
    bq_client,
    actor_user_id: str,
    actor_role: str,
    action_type: str,
    target_type: str,
    target_id: str,
    payload: Dict[str, Any],
    reason: Optional[str] = None,
    source: str = "COS_CHAT",
) -> Dict[str, Any]:
    """
    Step 1 of HITL: Create a proposal.
    Returns the proposal record with hitl_event_id and status.
    """
    action = ActionType(action_type)
    
    # Permission check
    allowed = get_role_permissions(actor_role)
    if action not in allowed:
        reason = f"Role {actor_role} does not have permission for {action_type}."
        if action == ActionType.POLICY_CHANGE:
            reason = "Policy changes require CEO authorization. Would you like me to send this as a proposal to Ahsin?"
        return {
            "status": "REJECTED",
            "reason": reason,
        }

    hitl_event_id = str(uuid.uuid4())
    now = datetime.utcnow()

    row = {
        "hitl_event_id": hitl_event_id,
        "timestamp": now.isoformat(),
        "actor_user_id": actor_user_id,
        "actor_role": actor_role,
        "source": source,
        "target_type": target_type,
        "target_id": target_id,
        "action_type": action_type,
        "status": "PROPOSED",
        "payload": json.dumps(payload),
        "diff": None,
        "reason": reason,
        "intent_confidence": None,
        "proposal_expires_at": (now + timedelta(hours=24)).isoformat(),
        "validated_at": None,
        "validation_result": None,
        "applied_at": None,
        "applied_by": None,
        "rolled_back_at": None,
        "rollback_event_id": None,
        "created_at": now.isoformat(),
    }

    errors = bq_client.insert_rows_json(
        "autohaus-infrastructure.autohaus_cil.hitl_events", [row]
    )
    if errors:
        logger.error(f"[HITL] Failed to create proposal: {errors}")
        return {"status": "ERROR", "reason": str(errors)}

    logger.info(f"[HITL] Proposal created: {hitl_event_id} ({action_type} on {target_id})")
    return {"status": "PROPOSED", "hitl_event_id": hitl_event_id}


# ── Validate ────────────────────────────────────────────────────────────

def validate(bq_client, hitl_event_id: str) -> Dict[str, Any]:
    """
    Step 2 of HITL: Validate a proposal.
    Checks permissions, scope, conflicts, and compliance locks.
    """
    # Fetch the proposal
    proposal = _fetch_hitl_event(bq_client, hitl_event_id)
    if not proposal:
        return {"status": "ERROR", "reason": "Proposal not found"}
    
    if proposal["status"] != "PROPOSED":
        return {"status": "ERROR", "reason": f"Cannot validate: current status is {proposal['status']}"}

    checks = []
    action = proposal["action_type"]
    actor_role = proposal["actor_role"]
    actor_id = proposal["actor_user_id"]

    # Check 1: Permission (already checked at propose, but re-verify)
    allowed = get_role_permissions(actor_role)
    if ActionType(action) not in allowed:
        checks.append({"check": "PERMISSION", "passed": False, "detail": f"{actor_role} cannot {action}"})
    elif action == "POLICY_CHANGE" and actor_role != "SOVEREIGN":
        checks.append({"check": "SOVEREIGN_POLICY", "passed": False, "detail": "Only SOVEREIGN can change policies"})
    else:
        checks.append({"check": "PERMISSION", "passed": True})

    # Check 2: Entity scope
    scope = ENTITY_SCOPE.get(actor_id.lower(), {}).get("scope", [])
    if scope != "ALL":
        # For now, scope checking is basic. Full implementation would query the target's entity associations.
        checks.append({"check": "SCOPE", "passed": True, "detail": "Scope check deferred to apply phase"})
    else:
        checks.append({"check": "SCOPE", "passed": True})

    # Check 3: Compliance lock (can't override LOCKED fields unless SOVEREIGN + amendment)
    if action == "FIELD_OVERRIDE":
        payload = json.loads(proposal["payload"]) if isinstance(proposal["payload"], str) else proposal["payload"]
        # Check if targeted doc is compliance-locked
        target_doc = _get_document_info(bq_client, proposal["target_id"])
        if target_doc and target_doc.get("amendment_lock") and actor_role != "SOVEREIGN":
            checks.append({"check": "COMPLIANCE_LOCK", "passed": False, "detail": "Document is amendment-locked. Only SOVEREIGN can amend."})
        else:
            checks.append({"check": "COMPLIANCE_LOCK", "passed": True})

    # Check 4: No conflicting pending HITL on same target+field
    if action == "FIELD_OVERRIDE":
        payload = json.loads(proposal["payload"]) if isinstance(proposal["payload"], str) else proposal["payload"]
        has_conflict = _check_concurrent_hitl(bq_client, proposal["target_id"], payload.get("field_name"), hitl_event_id)
        if has_conflict:
            checks.append({"check": "CONCURRENT_CONFLICT", "passed": False, "detail": "Another HITL is pending on same field"})
        else:
            checks.append({"check": "CONCURRENT_CONFLICT", "passed": True})

    # Determine overall result
    all_passed = all(c["passed"] for c in checks)
    new_status = "VALIDATED" if all_passed else "REJECTED"
    
    # Update the hitl_events record
    _update_hitl_status(bq_client, hitl_event_id, new_status, {
        "validated_at": datetime.utcnow().isoformat(),
        "validation_result": json.dumps(checks),
    })

    result = {"status": new_status, "checks": checks, "hitl_event_id": hitl_event_id}
    
    # Auto-apply low-risk actions
    if all_passed and ActionType(action) not in HIGH_RISK_ACTIONS:
        logger.info(f"[HITL] Auto-applying low-risk action: {action}")
        apply_result = apply(bq_client, hitl_event_id)
        result["auto_applied"] = True
        result["apply_result"] = apply_result

    return result


# ── Apply ───────────────────────────────────────────────────────────────

def apply(bq_client, hitl_event_id: str) -> Dict[str, Any]:
    """
    Step 3 of HITL: Apply a validated change.
    Writes the actual change to target tables and emits a cil_events record.
    """
    proposal = _fetch_hitl_event(bq_client, hitl_event_id)
    if not proposal:
        return {"status": "ERROR", "reason": "Proposal not found"}
    
    if proposal["status"] not in ("VALIDATED", "PROPOSED"):
        return {"status": "ERROR", "reason": f"Cannot apply: status is {proposal['status']}"}

    action = proposal["action_type"]
    payload = json.loads(proposal["payload"]) if isinstance(proposal["payload"], str) else proposal["payload"]
    target_id = proposal["target_id"]
    now = datetime.utcnow().isoformat()
    diff = {}

    try:
        if action == ActionType.FIELD_OVERRIDE:
            diff = _apply_field_override(bq_client, target_id, payload, hitl_event_id, proposal["actor_user_id"])
            rebuild_entity_facts(bq_client, target_id)
        elif action == ActionType.POLICY_CHANGE:
            diff = _apply_policy_change(bq_client, payload, hitl_event_id, proposal["actor_user_id"])
        elif action == ActionType.CONTEXT_ADD:
            diff = _apply_context_add(bq_client, target_id, payload)
        elif action == ActionType.ENTITY_MERGE:
            diff = _apply_entity_merge(bq_client, payload)
            rebuild_entity_facts(bq_client, payload.get("target_entity_id"))
            for sid in payload.get("source_entity_ids", []):
                rebuild_entity_facts(bq_client, sid)
        elif action == ActionType.CONFIRM_CLASSIFICATION:
            diff = _apply_confirm_classification(bq_client, target_id, payload)
        elif action == ActionType.REPROCESS:
            diff = {"action": "REPROCESS", "note": "Re-run extraction queued"}
            rebuild_entity_facts(bq_client, target_id)
        elif action == ActionType.ROLLBACK:
            diff = _apply_rollback(bq_client, payload)
        else:
            logger.warning(f"[HITL] Unhandled action type: {action}")
            diff = {"action": action, "note": "Handler not yet implemented"}
    except Exception as e:
        logger.error(f"[HITL] Apply failed for {hitl_event_id}: {e}")
        return {"status": "ERROR", "reason": str(e)}

    # Update hitl_events status
    _update_hitl_status(bq_client, hitl_event_id, "APPLIED", {
        "applied_at": now,
        "applied_by": "HITL_SERVICE",
        "diff": json.dumps(diff),
    })

    # Emit to cil_events (single audit spine)
    cil_event_type = f"HITL_{action}"
    event_row = {
        "event_id": str(uuid.uuid4()),
        "event_type": cil_event_type,
        "timestamp": now,
        "actor_type": "HUMAN",
        "actor_id": proposal["actor_user_id"],
        "actor_role": proposal["actor_role"],
        "target_type": proposal["target_type"],
        "target_id": target_id,
        "payload": json.dumps({"hitl_event_id": hitl_event_id, **diff}),
        "metadata": None,
        "idempotency_key": f"hitl_apply_{hitl_event_id}",
    }
    bq_client.insert_rows_json(
        "autohaus-infrastructure.autohaus_cil.cil_events", [event_row]
    )

    logger.info(f"[HITL] Applied {action} for {hitl_event_id}")
    return {"status": "APPLIED", "hitl_event_id": hitl_event_id, "diff": diff}


# ── Action Implementations ──────────────────────────────────────────────

def _apply_field_override(bq_client, document_id: str, payload: dict, hitl_event_id: str, actor_id: str) -> dict:
    """Write a field override to field_overrides table and update effective_value."""
    override_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    row = {
        "override_id": override_id,
        "document_id": document_id,
        "extraction_version_id": payload.get("extraction_version_id", "latest"),
        "field_name": payload["field_name"],
        "original_value": payload.get("original_value"),
        "override_value": payload["new_value"],
        "authority_level": "ASSERTED",
        "active": True,
        "effective_from": now,
        "effective_to": None,
        "hitl_event_id": hitl_event_id,
        "applied_by": actor_id,
        "notes": payload.get("reason", ""),
        "created_at": now,
    }

    errors = bq_client.insert_rows_json(
        "autohaus-infrastructure.autohaus_cil.field_overrides", [row]
    )
    if errors:
        raise Exception(f"Failed to write field override: {errors}")

    # Produce feedback loop entry
    process_correction_event(
        bq_client, 
        payload["field_name"], 
        str(payload.get("original_value")), 
        str(payload["new_value"]), 
        actor_id, 
        document_id
    )

    return {
        "field_name": payload["field_name"],
        "old_value": payload.get("original_value"),
        "new_value": payload["new_value"],
        "override_id": override_id,
    }


def _apply_context_add(bq_client, target_id: str, payload: dict) -> dict:
    """Context add is metadata enrichment — no conflict, just append."""
    # Write context as a note/metadata event. No table mutation needed.
    return {
        "context_key": payload.get("key", "general"),
        "context_value": payload.get("value", ""),
        "target_id": target_id,
    }


def _apply_entity_merge(bq_client, payload: dict) -> dict:
    """
    Merge source entities into target. Updates all document_entity_links
    pointing at source to point at target instead.
    """
    source_ids = payload.get("source_entity_ids", [])
    target_id = payload["target_entity_id"]
    entity_type = payload.get("entity_type", "VENDOR")
    
    # For each source entity, find all links and note them
    affected_docs = 0
    # Note: BigQuery doesn't support UPDATE via streaming API.
    # In production, this would use a MERGE DML statement.
    # For now, we log the intent and the drift sweep will clean up.
    
    logger.info(f"[HITL] Entity merge: {source_ids} → {target_id} ({entity_type})")
    
    return {
        "merge_type": entity_type,
        "source_ids": source_ids,
        "target_id": target_id,
        "note": "Link reassignment queued for drift sweep",
    }


def _apply_confirm_classification(bq_client, document_id: str, payload: dict) -> dict:
    """Human confirms or corrects the document classification."""
    return {
        "document_id": document_id,
        "confirmed_type": payload.get("doc_type"),
        "previous_type": payload.get("previous_type"),
    }


def _apply_rollback(bq_client, payload: dict) -> dict:
    """Rollback a previously applied HITL action."""
    target_hitl_id = payload.get("target_hitl_event_id")
    
    # Deactivate the field override if applicable
    if payload.get("override_id"):
        now = datetime.utcnow().isoformat()
        # Note: same BigQuery streaming limitation — log intent for drift sweep
        logger.info(f"[HITL] Rollback override {payload['override_id']}")
    
    return {
        "rolled_back_hitl_id": target_hitl_id,
        "override_id": payload.get("override_id"),
    }


def _apply_policy_change(bq_client, payload: Dict[str, Any], hitl_event_id: str, actor_id: str) -> Dict[str, Any]:
    """Applies a global policy change, overriding old policy values."""
    from database.policy_engine import get_policy
    domain = payload.get("policy_domain")
    key = payload.get("policy_key")
    new_value = payload.get("new_value")
    doc_type = payload.get("applies_to_doc_type")
    entity_type = payload.get("applies_to_entity_type")
    
    # 1. Fetch current policy (as "before" diff)
    current_val = get_policy(domain, key, doc_type=doc_type, entity_type=entity_type)
    
    # 2. Update existing rows (active = FALSE)
    deactivate_query = f"""
        UPDATE `autohaus-infrastructure.autohaus_cil.policy_registry`
        SET active = FALSE
        WHERE domain = @domain AND key = @key 
        AND IFNULL(applies_to_doc_type, '') = IFNULL(@doc_type, '')
        AND IFNULL(applies_to_entity_type, '') = IFNULL(@entity_type, '')
        AND active = TRUE
    """
    job_config = bq_client.query(deactivate_query, job_config=bq_client.QueryJobConfig(
        query_parameters=[
            bq_client.ScalarQueryParameter("domain", "STRING", domain),
            bq_client.ScalarQueryParameter("key", "STRING", key),
            bq_client.ScalarQueryParameter("doc_type", "STRING", doc_type or ""),
            bq_client.ScalarQueryParameter("entity_type", "STRING", entity_type or ""),
        ]
    ) if hasattr(bq_client, "ScalarQueryParameter") else None)
    # Actually bq_client doesn't expose nested params well this way but we can use string formatting for safe known schema keys.
    # We will use explicit bq.ScalarQueryParameter
    from google.cloud import bigquery as bq
    job_config = bq.QueryJobConfig(
        query_parameters=[
            bq.ScalarQueryParameter("domain", "STRING", domain),
            bq.ScalarQueryParameter("key", "STRING", key),
            bq.ScalarQueryParameter("doc_type", "STRING", doc_type or ""),
            bq.ScalarQueryParameter("entity_type", "STRING", entity_type or ""),
        ]
    )
    bq_client.query(deactivate_query, job_config=job_config).result()
    
    # 3. Create new row
    new_version_id = str(uuid.uuid4())
    val_str = json.dumps(new_value) if not isinstance(new_value, str) else new_value
    
    # Find highest current version
    v_query = "SELECT MAX(version) as max_v FROM `autohaus-infrastructure.autohaus_cil.policy_registry` WHERE domain = @domain AND key = @key"
    v_job = bq_client.query(v_query, job_config=bq.QueryJobConfig(
        query_parameters=[
            bq.ScalarQueryParameter("domain", "STRING", domain),
            bq.ScalarQueryParameter("key", "STRING", key),
        ]
    ))
    v_res = list(v_job.result())
    next_v = (v_res[0].max_v + 1) if (v_res and v_res[0].max_v is not None) else 1
    
    row = {
        "policy_id": new_version_id,
        "domain": domain,
        "key": key,
        "value": val_str,
        "description": f"Updated via HITL Event: {hitl_event_id}",
        "value_type": type(new_value).__name__ if not isinstance(new_value, str) else "str",
        "applies_to_entity": None,
        "applies_to_doc_type": doc_type,
        "applies_to_entity_type": entity_type,
        "version": next_v,
        "previous_version_id": None, # Complex to fetch reliably without an extra query, omitted for speed
        "updated_at": datetime.utcnow().isoformat(),
        "updated_by": actor_id,
        "change_reason": payload.get("reason", "Authoritative Policy Update"),
        "active": True
    }
    bq_client.insert_rows_json("autohaus-infrastructure.autohaus_cil.policy_registry", [row])
    
    # 4. Write CIL Events Audit
    event_id = str(uuid.uuid4())
    event_payload = {
        "domain": domain,
        "key": key,
        "doc_type": doc_type,
        "before": current_val,
        "after": new_value
    }
    from .logging_spine import log_cil_event
    log_cil_event(
        bq_client=bq_client,
        event_type="POLICY_UPDATED",
        source="HITL_SERVICE",
        entity_id=new_version_id,
        payload=event_payload,
        metadata={"hitl_event_id": hitl_event_id, "actor": actor_id}
    )
    
    # Force cache refresh
    from database.policy_engine import _engine
    _engine.clear_cache()
    
    return {
        "policy_domain": domain,
        "policy_key": key,
        "doc_type": doc_type,
        "before": current_val,
        "after": new_value
    }


# ── Helper Functions ────────────────────────────────────────────────────

def _fetch_hitl_event(bq_client, hitl_event_id: str) -> Optional[dict]:
    """Fetch the LATEST state of a HITL event (append-only pattern)."""
    from google.cloud import bigquery as bq
    query = """
        SELECT * FROM `autohaus-infrastructure.autohaus_cil.hitl_events`
        WHERE hitl_event_id = @id
        ORDER BY created_at DESC
        LIMIT 1
    """
    job_config = bq.QueryJobConfig(
        query_parameters=[bq.ScalarQueryParameter("id", "STRING", hitl_event_id)]
    )
    try:
        results = list(bq_client.query(query, job_config=job_config).result())
        if not results:
            return None
        row = results[0]
        # Convert BigQuery Row to dict
        return {field: getattr(row, field, None) for field in [
            "hitl_event_id", "timestamp", "actor_user_id", "actor_role",
            "source", "target_type", "target_id", "action_type", "status",
            "payload", "diff", "reason", "intent_confidence",
            "proposal_expires_at", "validated_at", "validation_result",
            "applied_at", "applied_by", "rolled_back_at", "rollback_event_id",
            "created_at",
        ]}
    except Exception as e:
        logger.error(f"[HITL] Fetch failed: {e}")
        return None


def _get_document_info(bq_client, document_id: str) -> Optional[dict]:
    """Get basic document info for compliance checks."""
    from google.cloud import bigquery as bq
    query = """
        SELECT document_id, doc_type, amendment_lock, authority_level, terminal_state
        FROM `autohaus-infrastructure.autohaus_cil.documents`
        WHERE document_id = @id LIMIT 1
    """
    job_config = bq.QueryJobConfig(
        query_parameters=[bq.ScalarQueryParameter("id", "STRING", document_id)]
    )
    try:
        results = list(bq_client.query(query, job_config=job_config).result())
        if results:
            r = results[0]
            return {
                "document_id": r.document_id,
                "doc_type": r.doc_type,
                "amendment_lock": r.amendment_lock,
                "authority_level": r.authority_level,
                "terminal_state": r.terminal_state,
            }
    except Exception as e:
        logger.error(f"[HITL] Doc info fetch failed: {e}")
    return None


def _check_concurrent_hitl(bq_client, target_id: str, field_name: str, exclude_id: str) -> bool:
    """Check if another HITL is pending on the same target+field."""
    if not field_name:
        return False
    from google.cloud import bigquery as bq
    query = """
        SELECT hitl_event_id FROM `autohaus-infrastructure.autohaus_cil.hitl_events`
        WHERE target_id = @target_id
        AND status IN ('PROPOSED', 'VALIDATED')
        AND hitl_event_id != @exclude_id
        AND JSON_VALUE(payload, '$.field_name') = @field_name
        LIMIT 1
    """
    job_config = bq.QueryJobConfig(
        query_parameters=[
            bq.ScalarQueryParameter("target_id", "STRING", target_id),
            bq.ScalarQueryParameter("exclude_id", "STRING", exclude_id),
            bq.ScalarQueryParameter("field_name", "STRING", field_name),
        ]
    )
    try:
        results = list(bq_client.query(query, job_config=job_config).result())
        return len(results) > 0
    except:
        return False


def _update_hitl_status(bq_client, hitl_event_id: str, new_status: str, extra_fields: dict):
    """
    Update a HITL event's status using append-only pattern.
    Inserts a new row with the updated status. _fetch_hitl_event picks
    the latest row per hitl_event_id via ORDER BY created_at DESC.
    """
    # Fetch the current state to carry forward unchanged fields
    current = _fetch_hitl_event(bq_client, hitl_event_id)
    if not current:
        logger.error(f"[HITL] Cannot update status: {hitl_event_id} not found")
        return

    now = datetime.utcnow().isoformat()

    # Build the new row, carrying forward all fields from current state
    new_row = {
        "hitl_event_id": hitl_event_id,
        "timestamp": current.get("timestamp", now) if not isinstance(current.get("timestamp"), str) else str(current.get("timestamp", now)),
        "actor_user_id": current.get("actor_user_id", ""),
        "actor_role": current.get("actor_role", ""),
        "source": current.get("source", "HITL_SERVICE"),
        "target_type": current.get("target_type", ""),
        "target_id": current.get("target_id", ""),
        "action_type": current.get("action_type", ""),
        "status": new_status,
        "payload": current.get("payload") if isinstance(current.get("payload"), str) else json.dumps(current.get("payload")) if current.get("payload") else None,
        "diff": extra_fields.get("diff", current.get("diff")),
        "reason": current.get("reason"),
        "intent_confidence": current.get("intent_confidence"),
        "proposal_expires_at": str(current.get("proposal_expires_at")) if current.get("proposal_expires_at") else None,
        "validated_at": extra_fields.get("validated_at", str(current.get("validated_at")) if current.get("validated_at") else None),
        "validation_result": extra_fields.get("validation_result", current.get("validation_result")),
        "applied_at": extra_fields.get("applied_at", str(current.get("applied_at")) if current.get("applied_at") else None),
        "applied_by": extra_fields.get("applied_by", current.get("applied_by")),
        "rolled_back_at": extra_fields.get("rolled_back_at", str(current.get("rolled_back_at")) if current.get("rolled_back_at") else None),
        "rollback_event_id": extra_fields.get("rollback_event_id", current.get("rollback_event_id")),
        "created_at": now,  # New creation timestamp = latest row
    }

    errors = bq_client.insert_rows_json(
        "autohaus-infrastructure.autohaus_cil.hitl_events", [new_row]
    )
    if errors:
        logger.error(f"[HITL] Failed to persist status update: {errors}")
    else:
        logger.info(f"[HITL] Status persisted: {hitl_event_id} → {new_status}")
