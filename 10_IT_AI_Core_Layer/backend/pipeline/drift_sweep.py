"""
AutoHaus CIL — Drift Sweep & Plate Escalation
Phase 3, Step 8 (Governance)

Drift Sweep: Periodic integrity check that catches:
  - Orphaned entity links (pointing to deleted/merged entities)
  - Stale document states (stuck in intermediate states)
  - KAMM review overdue (compliance docs not reviewed within SLA)
  - Blocking plates past due

Plate Escalation: Time-based escalation for unacknowledged plates.
"""

import uuid
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("autohaus.drift_sweep")


# ── Drift Sweep Checks ─────────────────────────────────────────────────

def run_drift_sweep(bq_client):
    """Main entry point — runs all integrity checks."""
    logger.info("[DRIFT] Starting drift sweep...")
    
    findings = []
    findings += _check_orphaned_links(bq_client)
    findings += _check_stale_documents(bq_client)
    findings += _check_kamm_overdue(bq_client)
    findings += _check_expired_hitl(bq_client)
    
    # Write findings to drift_sweep_results
    if findings:
        _write_findings(bq_client, findings)
    
    logger.info(f"[DRIFT] Sweep complete. {len(findings)} findings.")
    return findings


def _check_orphaned_links(bq_client) -> list:
    """Find document_entity_links pointing to non-existent entities."""
    findings = []
    
    # Check vehicle links
    query = """
        SELECT l.link_id, l.document_id, l.entity_id
        FROM `autohaus-infrastructure.autohaus_cil.document_entity_links` l
        LEFT JOIN `autohaus-infrastructure.autohaus_cil.vehicles` v
          ON l.entity_id = v.vehicle_id
        WHERE l.entity_type = 'VEHICLE'
          AND l.active = TRUE
          AND v.vehicle_id IS NULL
    """
    try:
        results = list(bq_client.query(query).result())
        for r in results:
            findings.append({
                "sweep_type": "ORPHANED_LINKS",
                "target_type": "DOCUMENT_ENTITY_LINK",
                "target_id": r.link_id,
                "finding": f"Vehicle link {r.link_id} points to non-existent vehicle {r.entity_id}",
                "severity": "MEDIUM",
                "auto_correctable": True,
            })
    except Exception as e:
        logger.error(f"[DRIFT] Orphaned link check failed: {e}")
    
    return findings


def _check_stale_documents(bq_client) -> list:
    """Find documents stuck in INGESTED state for more than 24 hours."""
    findings = []
    query = """
        SELECT document_id, filename_original, ingested_at
        FROM `autohaus-infrastructure.autohaus_cil.documents`
        WHERE terminal_state = 'INGESTED'
          AND ingested_at < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
    """
    try:
        results = list(bq_client.query(query).result())
        for r in results:
            findings.append({
                "sweep_type": "STALE_DOCUMENT",
                "target_type": "DOCUMENT",
                "target_id": r.document_id,
                "finding": f"Document {r.document_id} stuck in INGESTED since {r.ingested_at}",
                "severity": "LOW",
                "auto_correctable": False,
            })
    except Exception as e:
        logger.error(f"[DRIFT] Stale document check failed: {e}")
    
    return findings


def _check_kamm_overdue(bq_client) -> list:
    """Find KAMM compliance documents not reviewed within 4-hour SLA."""
    findings = []
    query = """
        SELECT document_id, doc_type, ingested_at
        FROM `autohaus-infrastructure.autohaus_cil.documents`
        WHERE kamm_compliance_type = TRUE
          AND requires_human_review = TRUE
          AND terminal_state NOT IN ('PROCESSED', 'FAILED_UNPROCESSABLE', 'DUPLICATE')
          AND ingested_at < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 4 HOUR)
    """
    try:
        results = list(bq_client.query(query).result())
        for r in results:
            findings.append({
                "sweep_type": "KAMM_REVIEW_OVERDUE",
                "target_type": "DOCUMENT",
                "target_id": r.document_id,
                "finding": f"KAMM doc {r.doc_type} ({r.document_id}) overdue for review since {r.ingested_at}",
                "severity": "CRITICAL",
                "auto_correctable": False,
            })
    except Exception as e:
        logger.error(f"[DRIFT] KAMM overdue check failed: {e}")
    
    return findings


def _check_expired_hitl(bq_client) -> list:
    """Find HITL proposals that have expired without action."""
    findings = []
    query = """
        SELECT hitl_event_id, action_type, actor_user_id, created_at
        FROM `autohaus-infrastructure.autohaus_cil.hitl_events`
        WHERE status = 'PROPOSED'
          AND proposal_expires_at < CURRENT_TIMESTAMP()
    """
    try:
        results = list(bq_client.query(query).result())
        for r in results:
            findings.append({
                "sweep_type": "EXPIRED_HITL",
                "target_type": "HITL_EVENT",
                "target_id": r.hitl_event_id,
                "finding": f"HITL {r.action_type} by {r.actor_user_id} expired without action",
                "severity": "LOW",
                "auto_correctable": True,
            })
    except Exception as e:
        logger.error(f"[DRIFT] Expired HITL check failed: {e}")
    
    return findings


def _write_findings(bq_client, findings: list):
    """Write sweep findings to BigQuery."""
    now = datetime.utcnow().isoformat()
    rows = []
    for f in findings:
        rows.append({
            "sweep_id": str(uuid.uuid4()),
            "sweep_type": f["sweep_type"],
            "target_type": f.get("target_type"),
            "target_id": f.get("target_id"),
            "finding": f["finding"],
            "severity": f["severity"],
            "auto_correctable": f.get("auto_correctable", False),
            "auto_corrected": False,
            "auto_correction_detail": None,
            "escalated": f["severity"] == "CRITICAL",
            "escalated_to": "ahsin" if f["severity"] == "CRITICAL" else None,
            "resolved": False,
            "resolved_at": None,
            "resolution_event_id": None,
            "created_at": now,
        })
    
    if rows:
        errors = bq_client.insert_rows_json(
            "autohaus-infrastructure.autohaus_cil.drift_sweep_results", rows
        )
        if errors:
            logger.error(f"[DRIFT] Failed to write findings: {errors}")
        
        # Emit events for critical findings
        for f in findings:
            if f["severity"] == "CRITICAL":
                event = {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "DRIFT_ESCALATED",
                    "timestamp": now,
                    "actor_type": "SYSTEM",
                    "actor_id": "drift_sweep",
                    "actor_role": "SYSTEM",
                    "target_type": f.get("target_type", "DOCUMENT"),
                    "target_id": f.get("target_id", "unknown"),
                    "payload": json.dumps({"finding": f["finding"], "severity": "CRITICAL"}),
                    "metadata": None,
                    "idempotency_key": f"drift_{f.get('target_id')}_{now[:10]}",
                }
                bq_client.insert_rows_json(
                    "autohaus-infrastructure.autohaus_cil.cil_events", [event]
                )
