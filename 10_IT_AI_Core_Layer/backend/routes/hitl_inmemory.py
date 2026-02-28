"""
AutoHaus CIL — In-Memory HITL Governance Store (Phase 9 Operational Bridge)
============================================================================
This router provides a fully functional in-memory HITL queue that unblocks
the UI governance flow (ActionCenter) while the BigQuery persistence layer
is being stabilized.

Endpoints:
  GET  /api/hitl/queue              — Returns all PENDING proposals
  POST /api/hitl/{event_id}/approve — Marks as APPROVED
  POST /api/hitl/{event_id}/reject  — Marks as REJECTED
  POST /api/hitl/enqueue            — Accepts new proposals into the queue
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("autohaus.hitl_inmemory")

hitl_inmemory_router = APIRouter(tags=["HITL-Live"])

# ── In-Memory Store ──────────────────────────────────────────────────────────
# Seeded with 3 representative proposals covering the key proposal types.
_store: Dict[str, dict] = {}


def _seed_store():
    """Seed the store with representative proposals for each card type."""
    seeds = [
        {
            "hitl_event_id": "seed-email-" + str(uuid.uuid4())[:8],
            "event_type": "EMAIL_DRAFTED",
            "action_type": "GMAIL_DRAFT_PROPOSAL",
            "target_type": "CONTACT",
            "target_id": "lead@example.com",
            "status": "PROPOSED",
            "reason": "AI drafted a follow-up email after 3-day lead silence",
            "payload": {
                "to": "lead@example.com",
                "subject": "Following up on your 2024 BMW X5 inquiry",
                "body": "Hi there,\n\nI wanted to follow up on your recent interest in the 2024 BMW X5. We have a few units available and I'd love to schedule a test drive at your convenience.\n\nBest regards,\nAutoHaus Team",
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "hitl_event_id": "seed-listing-" + str(uuid.uuid4())[:8],
            "event_type": "LISTING_SYNDICATION",
            "action_type": "ENTITY_MODIFICATION",
            "target_type": "VEHICLE",
            "target_id": "VIN-1HGBH41JXMN109186",
            "status": "PROPOSED",
            "reason": "Market scan detected 15% underpricing vs. comparable listings",
            "payload": {
                "field_name": "list_price",
                "original_value": "32500",
                "new_value": "37450",
                "confidence": "0.91",
                "data_source": "AutoTrader + Cars.com market scan",
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "hitl_event_id": "seed-journal-" + str(uuid.uuid4())[:8],
            "event_type": "FINANCIAL_JOURNAL",
            "action_type": "FINANCIAL_JOURNAL_PROPOSAL",
            "target_type": "ACCOUNT",
            "target_id": "QuickBooks-Sale-TXN-8821",
            "status": "PROPOSED",
            "reason": "Vehicle sale completed; AI proposes journal entry for revenue recognition",
            "payload": {
                "account": "4000 - Vehicle Sales Revenue",
                "debit": "Accounts Receivable",
                "credit": "Vehicle Sales Revenue",
                "amount": "$47,500.00",
                "memo": "Sale of 2022 Honda Accord EX-L, VIN 1HB...",
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    ]
    for s in seeds:
        _store[s["hitl_event_id"]] = s


_seed_store()


# ── Models ───────────────────────────────────────────────────────────────────

class EnqueueRequest(BaseModel):
    event_type: str
    action_type: str
    target_type: str
    target_id: str
    payload: Dict[str, Any]
    reason: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_event(event_id: str) -> dict:
    event = _store.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"HITL event '{event_id}' not found.")
    return event


def _assert_pending(event: dict):
    if event["status"] != "PROPOSED":
        raise HTTPException(
            status_code=409,
            detail=f"Event already resolved: status={event['status']}"
        )


# ── Routes ───────────────────────────────────────────────────────────────────

@hitl_inmemory_router.get("/hitl/queue")
async def get_queue() -> List[dict]:
    """Returns all PENDING proposals, sorted newest-first."""
    pending = [e for e in _store.values() if e["status"] == "PROPOSED"]
    pending.sort(key=lambda x: x["created_at"], reverse=True)
    # Ensure 'id' alias is always present for frontend compatibility
    for item in pending:
        item["id"] = item["hitl_event_id"]
    logger.info(f"[HITL-Live] Queue fetched: {len(pending)} pending")
    return pending


@hitl_inmemory_router.post("/hitl/{event_id}/approve")
async def approve_event(event_id: str):
    """Marks a proposal as APPROVED and removes it from the pending queue."""
    event = _get_event(event_id)
    _assert_pending(event)
    event["status"] = "APPLIED"
    event["applied_at"] = datetime.now(timezone.utc).isoformat()
    logger.info(f"[HITL-Live] APPROVED: {event_id}")
    return {
        "status": "APPLIED",
        "hitl_event_id": event_id,
        "message": "Proposal approved and applied successfully.",
    }


@hitl_inmemory_router.post("/hitl/{event_id}/reject")
async def reject_event(event_id: str, reason: Optional[str] = "Rejected by operator"):
    """Marks a proposal as REJECTED and archives it."""
    event = _get_event(event_id)
    _assert_pending(event)
    event["status"] = "REJECTED"
    event["rejected_at"] = datetime.now(timezone.utc).isoformat()
    event["rejection_reason"] = reason
    logger.info(f"[HITL-Live] REJECTED: {event_id} — {reason}")
    return {
        "status": "REJECTED",
        "hitl_event_id": event_id,
        "message": "Proposal rejected and archived.",
    }


@hitl_inmemory_router.post("/hitl/enqueue")
async def enqueue_proposal(request: EnqueueRequest):
    """Accepts a new proposal into the in-memory governance queue."""
    event_id = str(uuid.uuid4())
    event = {
        "hitl_event_id": event_id,
        "id": event_id,
        "event_type": request.event_type,
        "action_type": request.action_type,
        "target_type": request.target_type,
        "target_id": request.target_id,
        "status": "PROPOSED",
        "reason": request.reason,
        "payload": request.payload,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _store[event_id] = event
    logger.info(f"[HITL-Live] Enqueued: {event_id} ({request.action_type})")
    return {"status": "PROPOSED", "hitl_event_id": event_id}
