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

# Module 3: JIT Plate Protocol (ConnectionManager for browser push)
from routes.chat_stream import manager as ws_manager, build_plate_payload

# Module 4: Sovereign Memory
from memory.vector_vault import VectorVault

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


def _get_router() -> RouterAgent:
    global _router
    if _router is None:
        _router = RouterAgent()
    return _router


def _get_vault() -> VectorVault:
    global _vault
    if _vault is None:
        _vault = VectorVault()
    return _vault


# ---------------------------------------------------------------------------
# TwiML Response Builder
# ---------------------------------------------------------------------------
def build_twiml_reply(message: str) -> str:
    """
    Build a TwiML XML response for Twilio to send back as an SMS reply.

    Twilio expects the webhook to return TwiML (XML), not JSON.
    """
    escaped = (
        message
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
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
    """
    The primary Omnichannel Ear endpoint.

    Twilio sends a POST with form-encoded data when an SMS arrives.
    This handler chains all C-OS modules into a single pipeline.
    """
    phone_number = From.strip()
    message_body = Body.strip()
    timestamp = datetime.now(timezone.utc).isoformat()

    logger.info(f"[TWILIO] Inbound SMS from {phone_number}: '{message_body[:80]}'")

    if not message_body:
        twiml = build_twiml_reply("AutoHaus received your message, but it was empty. Please try again.")
        return Response(content=twiml, media_type="application/xml")

    # ── STEP 1: Identity Resolution (Module 1) ──────────────────────
    logger.info(f"[STEP 1] Resolving identity for {phone_number}")
    identity_result = IdentityEngine.resolve_identity(
        phone=phone_number,
        source_tag="TWILIO_SMS",
    )

    master_person_id = identity_result.get("master_person_id", "UNKNOWN")
    is_new_contact = identity_result.get("is_new", False)
    identity_confidence = identity_result.get("confidence_score", 0.0)

    if identity_result.get("status") == "error":
        logger.error(f"[STEP 1] Identity resolution failed: {identity_result}")
        master_person_id = "UNRESOLVED"

    logger.info(
        f"[STEP 1] Identity resolved: {master_person_id} "
        f"(new: {is_new_contact}, confidence: {identity_confidence})"
    )

    # ── STEP 2: Sovereign Memory Recall (Module 4) ──────────────────
    logger.info(f"[STEP 2] Recalling context from Vector Vault")
    vault = _get_vault()
    memory_context = vault.build_context_injection(message_body, top_k=3)

    if memory_context:
        logger.info(f"[STEP 2] Memory context injected ({len(memory_context)} chars)")
    else:
        logger.info("[STEP 2] No relevant memories found")

    # ── STEP 3: Agentic Router Classification (Module 2) ────────────
    # Enrich the message with memory context for smarter classification
    enriched_input = message_body
    if memory_context:
        enriched_input = f"{message_body}\n\n{memory_context}"

    logger.info(f"[STEP 3] Classifying intent via RouterAgent")
    router = _get_router()
    routed_intent = router.classify(enriched_input)

    intent = routed_intent.intent
    confidence = routed_intent.confidence
    target_entity = routed_intent.target_entity
    suggested_action = routed_intent.suggested_action

    logger.info(
        f"[STEP 3] Intent: {intent}, Confidence: {confidence}, "
        f"Target: {target_entity}"
    )

    # ── STEP 4: KAMM Compliance Fence ───────────────────────────────
    # Override: If SMS mentions titles/disclosures, force COMPLIANCE routing
    compliance_keywords = [
        "title", "damage disclosure", "dealer paperwork",
        "registration", "lien", "dmv", "iowa dot",
    ]
    if any(kw in message_body.lower() for kw in compliance_keywords):
        if intent != "COMPLIANCE":
            logger.info("[STEP 4] KAMM Compliance Fence triggered — overriding intent")
            intent = "COMPLIANCE"
            target_entity = "KAMM_LLC"
            suggested_action = "Route to KAMM Compliance for title/disclosure processing."

    # ── STEP 5: JIT Plate Push to Browser (Module 3) ────────────────
    # If any browser sessions are active, push a Plate to the UCC dashboard
    if ws_manager.active_count > 0:
        logger.info(f"[STEP 5] Pushing JIT Plate to {ws_manager.active_count} active client(s)")
        plate_payload = build_plate_payload(routed_intent)
        plate_payload["sms_source"] = phone_number
        plate_payload["master_person_id"] = master_person_id
        await ws_manager.broadcast(plate_payload)
    else:
        logger.info("[STEP 5] No active browser sessions — SMS-only response")

    # ── STEP 6: Build SMS Reply ─────────────────────────────────────
    brand = ENTITY_BRANDING.get(target_entity, "AutoHaus Command Center")

    if is_new_contact:
        greeting = "Welcome to AutoHaus! We've created your profile."
    else:
        greeting = "Thanks for reaching out."

    if confidence >= 0.7:
        reply_body = (
            f"{greeting}\n\n"
            f"I understood your request as: {intent.replace('_', ' ').title()}.\n"
            f"{suggested_action}\n\n"
            f"— {brand}"
        )
    else:
        reply_body = (
            f"{greeting}\n\n"
            f"I need a bit more detail to help you. "
            f"Could you clarify what you need? "
            f"(e.g., 'Check status on my BMW', 'Schedule an inspection')\n\n"
            f"— {brand}"
        )

    logger.info(f"[STEP 6] Replying to {phone_number} as '{brand}'")

    twiml = build_twiml_reply(reply_body)
    return Response(content=twiml, media_type="application/xml")
