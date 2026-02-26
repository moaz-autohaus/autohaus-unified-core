"""
AutoHaus C-OS v3.1 — MODULE 6: Omnichannel Ear (Twilio SMS Integration)
========================================================================
This module gives the Digital Chief of Staff the ability to "hear"
inbound SMS messages and "speak" back via Twilio. It is the full
integration layer that chains every prior module into a single pipeline:

  Inbound SMS → Identity Engine (Mod 1) → Sovereign Memory (Mod 4)
    → Agentic Router (Mod 2) → JIT Plate Push (Mod 3) → SMS Reply

Entity Branding Rules (from AUTOHAUS_SYSTEM_STATE.json v3.1.1-Alpha):
  - KAMM_LLC contexts → "KAMM Compliance" branding
  - AUTOHAUS_SERVICES_LLC contexts → "AutoHaus Service Lane" branding
  - ASTROLOGISTICS_LLC contexts → "AstroLogistics CVAD" branding
  - FLUIDITRUCK_LLC contexts → "Fluiditruck Fleet" branding
  - CARLUX_LLC contexts → "Carlux Logistics" branding
  - Default / CEO → "AutoHaus Command Center" branding

KAMM Compliance Fence:
  If the SMS mentions titles, damage disclosures, or dealer paperwork,
  the router MUST classify as COMPLIANCE and route to KAMM_LLC context.

Author: AutoHaus CIL Build System
Version: 1.0.0
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, Response, Form

# Module 1: Identity Resolution
from utils.identity_resolution import IdentityEngine

# Module 2: Agentic Router
from agents.router_agent import RouterAgent

# Module 1: Identity Resolution
from utils.identity_resolution import IdentityEngine

# Module 2: Agentic Router
from agents.router_agent import RouterAgent

# Module 3: JIT Plate Protocol (ConnectionManager for browser push)
from routes.chat_stream import manager as ws_manager, build_plate_payload

# Module 4: Sovereign Memory
from memory.vector_vault import VectorVault

# Module 9: Intelligent Membrane (IEA & CSM)
from agents.iea_agent import InputEnrichmentAgent, IEA_Result
from memory.csm import ConversationStateManager
from agents.attention_dispatcher import AttentionDispatcher

# ---------------------------------------------------------------------------
# Configuration & Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("autohaus.twilio_ear")

# Twilio credentials (loaded from environment)
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")

# Entity branding map for SMS reply signatures
ENTITY_BRANDING = {
    "KAMM_LLC": "KAMM Compliance",
    "AUTOHAUS_SERVICES_LLC": "AutoHaus Service Lane",
    "ASTROLOGISTICS_LLC": "AstroLogistics CVAD",
    "FLUIDITRUCK_LLC": "Fluiditruck Fleet",
    "CARLUX_LLC": "Carlux Logistics",
    "CARBON_LLC": "AutoHaus Command Center",
    "MAHAD_HOLDINGS_LLC": "Mahad Holdings",
}

# ---------------------------------------------------------------------------
# Lazy Singleton Instances (conserve Gemini quota)
# ---------------------------------------------------------------------------
_router: Optional[RouterAgent] = None
_vault: Optional[VectorVault] = None
_iea: Optional[InputEnrichmentAgent] = None
_csm: Optional[ConversationStateManager] = None
_dispatcher: Optional[AttentionDispatcher] = None

def _get_router() -> RouterAgent:
    global _router
    if _router is None: _router = RouterAgent()
    return _router

def _get_vault() -> VectorVault:
    global _vault
    if _vault is None: _vault = VectorVault()
    return _vault

def _get_iea() -> InputEnrichmentAgent:
    global _iea
    if _iea is None: _iea = InputEnrichmentAgent()
    return _iea

def _get_csm() -> ConversationStateManager:
    global _csm
    if _csm is None: _csm = ConversationStateManager()
    return _csm

def _get_dispatcher() -> AttentionDispatcher:
    global _dispatcher
    if _dispatcher is None: _dispatcher = AttentionDispatcher()
    return _dispatcher


# ---------------------------------------------------------------------------
# TwiML Response Builder
# ---------------------------------------------------------------------------
def build_twiml_reply(message: str) -> str:
    escaped = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{escaped}</Message>
</Response>"""


# ---------------------------------------------------------------------------
# FastAPI Router
# ---------------------------------------------------------------------------
twilio_router = APIRouter()


@twilio_router.post("/webhooks/twilio/sms")
async def handle_inbound_sms(
    request: Request,
    From: str = Form(""),
    Body: str = Form(""),
    To: str = Form(""),
):
    phone_number = From.strip()
    raw_message_body = Body.strip()
    
    logger.info(f"[TWILIO] Inbound SMS from {phone_number}: '{raw_message_body[:80]}'")
    if not raw_message_body:
        return Response(content=build_twiml_reply("Empty message."), media_type="application/xml")

    # ── STEP 1: Identity Resolution (Module 1) ──────────────────────
    identity_result = IdentityEngine.resolve_identity(phone=phone_number, source_tag="TWILIO_SMS")
    master_person_id = identity_result.get("master_person_id", "UNKNOWN")

    # ── STEP 2: Intelligent Membrane - CSM Resume ───────────────────
    csm = _get_csm()
    active_state = csm.get_state(user_id=phone_number)
    
    message_body_for_iea = raw_message_body
    if active_state:
        logger.info(f"[MEMBRANE] Resuming suspended context for {phone_number}: {active_state}")
        # Prepend the previous gathered info so the IEA knows this is a follow-up
        message_body_for_iea = f"Previous Context: {active_state['collected_entities']}. New Input: {raw_message_body}"

    # ── STEP 3: Intelligent Membrane - IEA Enrichment ───────────────
    logger.info("[MEMBRANE] Routing through Input Enrichment Agent (IEA)")
    iea = _get_iea()
    iea_result: IEA_Result = iea.evaluate(message_body_for_iea, previous_context=active_state)
    
    if iea_result.status == "INCOMPLETE":
        logger.warning(f"[MEMBRANE] Input incomplete. Triggering CSM hold. Clarification: {iea_result.clarifying_question}")
        # Save to Waiting Room
        csm.set_state(
            user_id=phone_number,
            session_state="PENDING_CLARIFICATION",
            pending_intent="UNKNOWN",
            collected_entities=iea_result.extracted_entities
        )
        return Response(content=build_twiml_reply(iea_result.clarifying_question), media_type="application/xml")
    
    # If we made it here, the input is COMPLETE. Clear the waiting room.
    csm.clear_state(user_id=phone_number)

    # ── STEP 4: Sovereign Memory Recall (Module 4) ──────────────────
    vault = _get_vault()
    memory_context = vault.build_context_injection(raw_message_body, top_k=3)
    enriched_input = raw_message_body
    if memory_context:
        enriched_input = f"{raw_message_body}\n\n{memory_context}"

    # ── STEP 5: Agentic Router Classification (Module 2) ────────────
    router = _get_router()
    routed_intent = router.classify(enriched_input)
    
    intent = routed_intent.intent
    target_entity = routed_intent.target_entity
    suggested_action = routed_intent.suggested_action

    # ── STEP 6: KAMM Compliance Fence ───────────────────────────────
    if any(kw in raw_message_body.lower() for kw in ["title", "disclosure", "dot", "registration"]):
        intent, target_entity = "COMPLIANCE", "KAMM_LLC"

    # ── STEP 7: Attention Dispatcher (Module 9) ─────────────────────
    dispatcher = _get_dispatcher()
    event_desc = f"User {master_person_id} requested {intent} action: {suggested_action}"
    attention_result = dispatcher.evaluate_event(event_desc)
    
    # ── STEP 8: Route Output based on Attention Score ────────────────
    plate_payload = build_plate_payload(routed_intent)
    plate_payload["sms_source"] = phone_number
    plate_payload["master_person_id"] = master_person_id
    
    if attention_result.route == "WEBSOCKET" and ws_manager.active_count > 0:
        # Route 1: Desk - Push to UI silently
        logger.info(f"[DISPATCHER] Low Urgency ({attention_result.urgency_score}/10). Pushing to UI.")
        await ws_manager.broadcast(plate_payload)
        response_text = "" # Don't text Ahsin, he's seeing it on the screen
    else:
        # Route 2: Pocket - Send SMS
        logger.info(f"[DISPATCHER] High Urgency or No UI ({attention_result.urgency_score}/10). Sending SMS.")
        brand = ENTITY_BRANDING.get(target_entity, "AutoHaus Command Center")
        response_text = f"{attention_result.synthesized_message}\n\n— {brand}"
        
        # Still push to WS for the audit trail
        if ws_manager.active_count > 0:
             await ws_manager.broadcast(plate_payload)

    # Note: Twilio requires non-empty responses, or it will throw an error, 
    # but an empty <Message></Message> acts as a "silent acknowledge"
    return Response(content=build_twiml_reply(response_text), media_type="application/xml")
