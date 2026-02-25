from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from utils.identity_resolution import IdentityEngine
from agents.attention_dispatcher import AttentionDispatcher
from routes.chat_stream import manager, _resolve_skin

identity_router = APIRouter()
attention_dispatcher = AttentionDispatcher()

class LeadIntakeRequest(BaseModel):
    source: str
    email: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

async def trigger_membrane_attention(payload: LeadIntakeRequest, identity_result: dict):
    """
    Asynchronous background task to trigger Attention Dispatcher and push a JIT Plate
    if a new lead is flagged.
    """
    # Only aggressively notify on highly relevant new leads, or we can just send it to dashboard
    is_new = identity_result.get("is_new", False)
    universal_id = identity_result.get("master_person_id", "Unknown")
    
    event_desc = (
        f"{'New' if is_new else 'Returning'} lead inbound from {payload.source}. "
        f"Name: {payload.first_name or ''} {payload.last_name or ''}. "
        f"Contact: {payload.email or ''} | {payload.phone or ''}. "
        f"Assigned Universal ID: {universal_id}"
    )

    attention_result = attention_dispatcher.evaluate_event(event_desc)

    # Build the JIT Plate with nested strategy block
    plate_payload = {
        "type": "MOUNT_PLATE",
        "plate_id": "CRM_PROFILE",
        "intent": "CRM",
        "confidence": identity_result.get("confidence_score", 1.0),
        "entities": {
            "first_name": payload.first_name,
            "last_name": payload.last_name,
            "email": payload.email,
            "phone": payload.phone,
            "source": payload.source,
            "universal_id": universal_id,
            "is_new": is_new
        },
        "target_entity": payload.source,
        "suggested_action": attention_result.synthesized_message,
        "strategy": _resolve_skin(attention_result.urgency_score, payload.source),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": [] 
    }

    # If it's very urgent, we could hypothetically use Twilio SMS here if route == "SMS".
    # For now, we always broadcast the new lead to the websocket (System Ledger / Dashboard).
    await manager.broadcast(plate_payload)


@identity_router.post("/intake")
async def process_crm_intake(payload: LeadIntakeRequest, background_tasks: BackgroundTasks):
    """
    Module 1: Identity Bedrock CRM Intake Endpoint
    Processes inbound leads and merges/resolves them against the Human Graph (BigQuery).
    Returns the Universal Master Person ID and confidence score.
    """
    if not payload.email and not payload.phone:
        raise HTTPException(
            status_code=400, 
            detail="Must provide at least email or phone for probabilistic identity resolution."
        )
        
    try:
        # Perform Probabilistic Identity Resolution
        result = IdentityEngine.resolve_identity(
            email=payload.email,
            phone=payload.phone,
            first_name=payload.first_name,
            last_name=payload.last_name,
            source_tag=payload.source
        )
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
            
        # Hook into Intelligent Membrane / Attention Dispatcher
        background_tasks.add_task(trigger_membrane_attention, payload, result)
            
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal CRM Intake Error: {str(e)}")
