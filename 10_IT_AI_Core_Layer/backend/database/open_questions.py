"""
AutoHaus CIL — Native Governance Open Questions Engine (Pass 7)
"""

import uuid
import json
import logging
from datetime import datetime
from .policy_engine import get_policy

logger = logging.getLogger("autohaus.open_questions")

def raise_open_question(bq_client, question_type: str, priority: str, context: dict, description: str):
    """Raises an open question to the HITL/CoS layer instead of silently failing."""
    
    # Check policy for snooze/escalation defaults
    snooze_hours = int(get_policy("ESCALATION", "snooze_duration_hours") or 24)
    
    row = {
        "question_id": str(uuid.uuid4()),
        "question_type": question_type,
        "priority": priority, # HIGH, MEDIUM, LOW
        "status": "OPEN",
        "context": json.dumps(context),
        "description": description,
        "assigned_to": None,
        "escalation_target": "CEO",
        "due_by": None, # Could be set here based on max_overdue_hours
        "created_at": datetime.utcnow().isoformat(),
        "resolved_at": None,
        "resolution_event_id": None
    }
    
    # Also emit an event
    event_row = {
        "event_id": str(uuid.uuid4()),
        "event_type": "QUESTION_RAISED", 
        "timestamp": row["created_at"],
        "actor_type": "SYSTEM",
        "actor_id": "open_questions_engine",
        "actor_role": "SYSTEM",
        "target_type": "QUESTION",
        "target_id": row["question_id"],
        "payload": json.dumps(row),
        "metadata": None,
        "idempotency_key": f"qr_{row['question_id']}"
    }
    
    try:
        # BQ requires the table to exist
        q_errs = bq_client.insert_rows_json("autohaus-infrastructure.autohaus_cil.open_questions", [row])
        if q_errs: logger.error(f"[QUESTION] Insert Error: {q_errs}")
        e_errs = bq_client.insert_rows_json("autohaus-infrastructure.autohaus_cil.cil_events", [event_row])
        if e_errs: logger.error(f"[QUESTION] Event Error: {e_errs}")
        
        logger.warning(f"[QUESTION] Raised: {description}")
    except Exception as e:
        logger.error(f"[QUESTION] Failed to raise open question: {e}")
