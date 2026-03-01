"""
AutoHaus CIL — Native Governance Open Questions Engine (Pass 7 + WS Broadcast)
"""

import asyncio
import uuid
import json
import logging
from datetime import datetime, timezone, timedelta
from .policy_engine import get_policy

logger = logging.getLogger("autohaus.open_questions")

PRIORITY_TO_OWNER_ROLE = {
    "HIGH": "SOVEREIGN",
    "MEDIUM": "STANDARD",
    "LOW": "FIELD",
}

PRIORITY_TO_SLA_HOURS = {
    "HIGH": 4,
    "MEDIUM": 24,
    "LOW": 72,
}

ACCESS_RANK = {
    "SOVEREIGN": 3,
    "STANDARD": 2,
    "FIELD": 1,
}

SOURCE_TYPE_MAP = {
    "CONFLICTING_CLAIM": "CONFLICT",
    "INVALID_EDGE": "ASSERTION",
    "IEA_MISMATCH": "IEA",
    "MANUAL": "MANUAL",
}


def raise_open_question(bq_client, question_type: str, priority: str, context: dict, description: str):
    """Raises an open question to the HITL/CoS layer and broadcasts via WebSocket."""

    snooze_hours = int(get_policy("ESCALATION", "snooze_duration_hours") or 24)
    sla_hours = PRIORITY_TO_SLA_HOURS.get(priority, 24)
    now_utc = datetime.now(timezone.utc)
    due_at = now_utc + timedelta(hours=sla_hours)
    owner_role = PRIORITY_TO_OWNER_ROLE.get(priority, "STANDARD")
    source_type = SOURCE_TYPE_MAP.get(question_type, "MANUAL")

    row = {
        "question_id": str(uuid.uuid4()),
        "question_type": question_type,
        "priority": priority,
        "status": "OPEN",
        "context": json.dumps(context),
        "description": description,
        "assigned_to": None,
        "escalation_target": "CEO",
        "due_by": due_at.isoformat(),
        "created_at": now_utc.isoformat(),
        "resolved_at": None,
        "resolution_event_id": None
    }

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
        q_errs = bq_client.insert_rows_json("autohaus-infrastructure.autohaus_cil.open_questions", [row])
        if q_errs:
            logger.error(f"[QUESTION] Insert Error: {q_errs}")
        e_errs = bq_client.insert_rows_json("autohaus-infrastructure.autohaus_cil.cil_events", [event_row])
        if e_errs:
            logger.error(f"[QUESTION] Event Error: {e_errs}")

        logger.warning(f"[QUESTION] Raised: {description}")
    except Exception as e:
        logger.error(f"[QUESTION] Failed to raise open question: {e}")

    ws_payload = {
        "type": "OPEN_QUESTION",
        "question_id": row["question_id"],
        "content": description,
        "owner_role": owner_role,
        "source_type": source_type,
        "sla_hours": sla_hours,
        "due_at": due_at.isoformat(),
        "dependency_list": context.get("dependency_list", []),
        "created_at": row["created_at"],
    }

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_broadcast_open_question(ws_payload, owner_role))
    except RuntimeError:
        logger.debug("[QUESTION] No running event loop — WS broadcast skipped (sync caller)")


async def _broadcast_open_question(payload: dict, owner_role: str):
    """Broadcast an OPEN_QUESTION to all connected clients with sufficient access."""
    try:
        from routes.chat_stream import manager
        min_rank = ACCESS_RANK.get(owner_role, 0)
        for client_id, meta in manager.get_clients_with_access().items():
            client_rank = ACCESS_RANK.get(meta.get("access", ""), 0)
            if client_rank >= min_rank:
                ws = manager._active_connections.get(client_id)
                if ws:
                    await ws.send_json(payload)
        logger.info(f"[QUESTION] Broadcast OPEN_QUESTION {payload['question_id']} to clients with access >= {owner_role}")
    except Exception as e:
        logger.error(f"[QUESTION] WS broadcast failed: {e}")
