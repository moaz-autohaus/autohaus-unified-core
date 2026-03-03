
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Response, Form
from utils.identity_resolution import IdentityEngine
from membrane.session_context import SessionContext
from membrane.router_gateway import RouterGateway
from membrane.channel_selector import ChannelSelector

logger = logging.getLogger("autohaus.membrane.twilio_gateway")
twilio_router = APIRouter()

class TwilioGateway:
    """
    Membrane Layer: The entry point for inbound SMS.
    Handles number-to-actor resolution and session orchestration.
    """
    
    def __init__(self):
        self.router_gate = RouterGateway()
        self.selector = ChannelSelector()

    async def handle_inbound(self, from_number: str, body: str) -> str:
        """
        Orchestrates the lifecycle of an SMS message.
        """
        # 1. Number-to-Actor Resolution (Membrane)
        identity = IdentityEngine.resolve_identity(phone=from_number, source_tag="TWILIO_SMS")
        user_id = identity.get("master_person_id", "UNKNOWN")
        
        # 2. Session Context (Membrane)
        session = SessionContext.create_session(user_id=user_id)
        
        # 3. Call Router Gateway (Membrane -> CIL -> Membrane)
        # This handles intent classification, scope enforcement, and delivery signals.
        decision = await self.router_gate.handle_input(session, body)
        
        # 4. SMS Delivery Decision
        if decision["status"] == "BLOCKED":
            return decision["message"]
        elif decision["status"] == "CLARIFY":
            return decision["message"]
        
        # If ALLOWED, the domain agents will eventually handle it.
        # For now, return the routing message.
        return decision.get("message", "Processing your request...")

@twilio_router.post("/webhooks/twilio/sms")
async def twilio_webhook(From: str = Form(""), Body: str = Form("")):
    gateway = TwilioGateway()
    reply = await gateway.handle_inbound(From, Body)
    
    # Return TwiML
    return Response(content=f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{reply}</Message>
</Response>""", media_type="application/xml")
