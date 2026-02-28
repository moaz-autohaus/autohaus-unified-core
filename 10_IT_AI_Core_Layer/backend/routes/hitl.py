import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger("autohaus.hitl")

hitl_router = APIRouter()

_queue: dict[str, dict] = {}


class HitlEvent(BaseModel):
    event_id: Optional[str] = None
    event_type: str
    payload: dict
    entity_context: Optional[str] = None


def _seed_defaults():
    if _queue:
        return
    defaults = [
        {
            "event_id": "evt_001",
            "event_type": "EMAIL_DRAFTED",
            "status": "PENDING",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "entity_context": "KAMM_LLC",
            "payload": {
                "recipient_email": "buyer@example.com",
                "subject": "Your 2023 BMW M4 Competition — Purchase Confirmation",
                "body": "Dear Valued Customer,\n\nThank you for your purchase of the 2023 BMW M4 Competition (VIN: WBA93HM0XP1234567). We are pleased to confirm your transaction has been processed.\n\nPlease find the attached title transfer documentation...",
            },
        },
        {
            "event_id": "evt_002",
            "event_type": "LISTING_PROPOSED",
            "status": "PENDING",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "entity_context": "AUTOHAUS_SVC",
            "payload": {
                "vin": "5YJSA1E26MF123456",
                "vehicle": "2022 Tesla Model S Plaid",
                "year": 2022,
                "make": "Tesla",
                "model": "Model S Plaid",
                "platforms": ["CarGurus", "Facebook Marketplace", "AutoTrader"],
                "description": "Pristine 2022 Tesla Model S Plaid — Midnight Silver Metallic with White Interior. One Owner, Clean Title, Full Service History. 1,020 HP Tri-Motor AWD.",
            },
        },
        {
            "event_id": "evt_003",
            "event_type": "QUICKBOOKS_JOURNAL_PROPOSED",
            "status": "PENDING",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "entity_context": "CARBON_LLC",
            "payload": {
                "description": "Vehicle Purchase — 2022 Ford F-150 Raptor",
                "amount": 15000,
                "account": "1400 (Inventory)",
                "entity": "FLUIDITRUCK_LLC",
            },
        },
    ]
    for evt in defaults:
        _queue[evt["event_id"]] = evt


@hitl_router.get("/queue")
async def get_hitl_queue():
    _seed_defaults()
    pending = [v for v in _queue.values() if v.get("status") == "PENDING"]
    pending.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    return pending


@hitl_router.post("/enqueue")
async def enqueue_event(event: HitlEvent):
    eid = event.event_id or f"evt_{uuid.uuid4().hex[:8]}"
    record = {
        "event_id": eid,
        "event_type": event.event_type,
        "status": "PENDING",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "entity_context": event.entity_context,
        "payload": event.payload,
    }
    _queue[eid] = record
    logger.info(f"[HITL] Enqueued {eid} ({event.event_type})")
    return record


@hitl_router.post("/{event_id}/approve")
async def approve_event(event_id: str):
    _seed_defaults()
    evt = _queue.get(event_id)
    if not evt:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    if evt["status"] != "PENDING":
        raise HTTPException(status_code=409, detail=f"Event {event_id} already resolved ({evt['status']})")
    evt["status"] = "APPROVED"
    evt["resolved_at"] = datetime.now(timezone.utc).isoformat()
    evt["resolved_by"] = "CIL_GOVERNANCE"
    logger.info(f"[HITL] Approved {event_id} ({evt['event_type']})")
    return {"status": "approved", "event_id": event_id, "message": f"{evt['event_type']} executed successfully."}


@hitl_router.post("/{event_id}/reject")
async def reject_event(event_id: str):
    _seed_defaults()
    evt = _queue.get(event_id)
    if not evt:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    if evt["status"] != "PENDING":
        raise HTTPException(status_code=409, detail=f"Event {event_id} already resolved ({evt['status']})")
    evt["status"] = "REJECTED"
    evt["resolved_at"] = datetime.now(timezone.utc).isoformat()
    evt["resolved_by"] = "CIL_GOVERNANCE"
    logger.info(f"[HITL] Rejected {event_id} ({evt['event_type']})")
    return {"status": "rejected", "event_id": event_id, "message": f"{evt['event_type']} archived."}
