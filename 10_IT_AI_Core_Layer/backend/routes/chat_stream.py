"""
AutoHaus C-OS v3.1 — MODULE 3: JIT Plate Protocol (WebSocket Chat Stream)
==========================================================================
This module is the "Nervous System" of the Conversational Operating System.
It maintains persistent WebSocket connections between the Python CIL backend
and the React frontend (UCC), enabling the Digital Chief of Staff to push
JIT UI Plates in real-time without page refreshes.

Architecture:
  1. Client connects to /ws/chat
  2. Client sends a natural language message (JSON: {"message": "..."})
  3. The RouterAgent classifies intent and extracts entities
  4. The backend pushes back a MOUNT_PLATE command with hydrated data
  5. React dynamically renders the correct Plate component

Plate Types:
  - FINANCE_CHART:        Revenue/cost visualization for a lane or entity
  - INVENTORY_TABLE:      Vehicle inventory data grid
  - SERVICE_TIMELINE:     Active repair orders and recon status
  - CRM_PROFILE:          Customer identity card from the Human Graph
  - LOGISTICS_MAP:        Live driver tracking and dispatch board
  - COMPLIANCE_CHECKLIST: Title/disclosure document status
  - CHAT_RESPONSE:        Simple text reply (no Plate needed)
  - AMBIGUITY_RESOLUTION: Multi-choice selector for collisions

Author: AutoHaus CIL Build System
Version: 1.0.0
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import google.generativeai as genai

# C-OS Modules
from agents.router_agent import RouterAgent, RoutedIntent
from memory.vector_vault import VectorVault
from agents.iea_agent import InputEnrichmentAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("autohaus.chat_stream")


# ---------------------------------------------------------------------------
# Plate Mapping: Intent Domain → React UI Component
# ---------------------------------------------------------------------------
PLATE_MAP = {
    "FINANCE":    "FINANCE_CHART",
    "INVENTORY":  "INVENTORY_TABLE",
    "SERVICE":    "SERVICE_TIMELINE",
    "CRM":        "CRM_PROFILE",
    "LOGISTICS":  "LOGISTICS_MAP",
    "COMPLIANCE": "COMPLIANCE_CHECKLIST",
    "UNKNOWN":    "CHAT_RESPONSE",
}


# ---------------------------------------------------------------------------
# WebSocket Connection Manager
# ---------------------------------------------------------------------------
class ConnectionManager:
    """
    Manages active WebSocket connections for the C-OS.

    Each connected client (browser tab, mobile app, etc.) is tracked by a
    unique client_id derived from their WebSocket session. This enables
    targeted "push" messages to specific users (e.g., alert only the CEO).
    """

    def __init__(self):
        self._active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self._active_connections[client_id] = websocket
        logger.info(f"Client connected: {client_id} (Total: {len(self._active_connections)})")

    def disconnect(self, client_id: str):
        """Remove a disconnected client."""
        self._active_connections.pop(client_id, None)
        logger.info(f"Client disconnected: {client_id} (Total: {len(self._active_connections)})")

    async def send_personal_message(self, message: dict, client_id: str):
        """Push a JSON message to a specific connected client."""
        ws = self._active_connections.get(client_id)
        if ws:
            await ws.send_json(message)

    async def broadcast(self, message: dict):
        """Push a JSON message to ALL connected clients (e.g., system alerts)."""
        for client_id, ws in self._active_connections.items():
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error(f"Broadcast failed for {client_id}: {e}")

    @property
    def active_count(self) -> int:
        return len(self._active_connections)


# ---------------------------------------------------------------------------
# Singleton Instances
# ---------------------------------------------------------------------------
manager = ConnectionManager()

# Lazy-initialized RouterAgent (only created on first message to conserve quota)
_router: Optional[RouterAgent] = None


def _get_router() -> RouterAgent:
    """Lazy singleton for the RouterAgent to avoid initializing Gemini on import."""
    global _router
    if _router is None:
        _router = RouterAgent()
    return _router


# ---------------------------------------------------------------------------
# Skin Selection Logic (Backend decides, Frontend obeys)
# ---------------------------------------------------------------------------
def _resolve_skin(urgency_score: int, target_entity: str) -> dict:
    """
    The Backend is the single source of truth for the visual expression.
    This function maps urgency and context to a UI Strategy directive.
    """
    if urgency_score >= 8:
        return {
            "skin": "FIELD_DIAGNOSTIC",
            "urgency": urgency_score,
            "vibration": True,
            "overlay": "porsche-red-pulse",
        }
    elif target_entity in ("CLIENT", "EXTERNAL", "WEB_LEAD"):
        return {
            "skin": "CLIENT_HANDSHAKE",
            "urgency": urgency_score,
            "vibration": False,
            "overlay": None,
        }
    elif urgency_score <= 2:
        return {
            "skin": "GHOST",
            "urgency": urgency_score,
            "vibration": False,
            "overlay": None,
        }
    else:
        return {
            "skin": "SUPER_ADMIN",
            "urgency": urgency_score,
            "vibration": False,
            "overlay": None,
        }


# ---------------------------------------------------------------------------
# JIT Plate Builder
# ---------------------------------------------------------------------------
def build_plate_payload(routed: RoutedIntent, urgency_score: int = 5) -> dict:
    """
    Translate a RoutedIntent into a JIT Plate mount command for the React UI.

    The React <PlateHydrator /> component listens for these payloads and
    dynamically imports and renders the correct visualization component.

    The nested `strategy` block makes the frontend truly stateless —
    it never has to guess which skin to use.
    """
    plate_id = PLATE_MAP.get(routed.intent, "CHAT_RESPONSE")

    # If confidence is low, override to ambiguity resolution
    if routed.confidence < 0.7 and routed.intent != "UNKNOWN":
        plate_id = "AMBIGUITY_RESOLUTION"

    # Backend resolves the skin — frontend is dumb
    strategy = _resolve_skin(urgency_score, routed.target_entity)

    payload = {
        "type": "MOUNT_PLATE",
        "plate_id": plate_id,
        "intent": routed.intent,
        "confidence": routed.confidence,
        "entities": routed.entities,
        "target_entity": routed.target_entity,
        "suggested_action": routed.suggested_action,
        "strategy": strategy,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": [],  # Placeholder: hydrated with BigQuery data in future modules
    }

    return payload


# ---------------------------------------------------------------------------
# Message Processor
# ---------------------------------------------------------------------------
async def process_incoming_message(websocket: WebSocket, client_id: str, text_data: str):
    """Processes an incoming chat message using the C-OS pipeline."""
    logger.info(f"[WS] Received message: '{text_data[:80]}...'")

    # 1. Sovereign Memory context injection
    from memory.vector_vault import VectorVault
    vault = VectorVault()
    memory_context = vault.build_context_injection(text_data, top_k=3)

    enriched_input = text_data
    if memory_context:
        logger.info(f"[WS] Found historical context.")
        enriched_input = f"{text_data}\n\n{memory_context}"

    # 2. Intelligent Membrane: IEA Enrichment
    from agents.iea_agent import InputEnrichmentAgent
    iea = InputEnrichmentAgent()
    logger.info("[WS] Passing through IEA Membrane")
    iea_result = iea.evaluate(enriched_input)

    if iea_result.status == "INCOMPLETE":
        logger.warning(f"[WS] Membrane caught incomplete input: {iea_result.clarifying_question}")
        # If incomplete, bypass the Router and ask the user directly
        clarification_payload = {
            "type": "MOUNT_PLATE",
            "plate_id": "CHAT_RESPONSE",
            "intent": "CLARIFICATION_REQUIRED",
            "confidence": 1.0,
            "entities": iea_result.extracted_entities,
            "target_entity": "CARBON_LLC",
            "suggested_action": iea_result.clarifying_question,
            "strategy": _resolve_skin(5, "CARBON_LLC"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dataset": []
        }
        await manager.send_personal_message(clarification_payload, client_id)
        return

    # 3. Classify structured input via RouterAgent
    from agents.router_agent import RouterAgent
    router = _get_router()
    logger.info("[WS] Classifying intent.")
    routed_intent = router.classify(enriched_input)

    # 4. Determine Urgency via Attention Dispatcher
    from agents.attention_dispatcher import AttentionDispatcher
    dispatcher = AttentionDispatcher()
    attention_result = dispatcher.evaluate_event(enriched_input)

    # 5. Generate the JIT Plate JSON payload
    plate_payload = build_plate_payload(routed_intent, urgency_score=attention_result.urgency_score)

    # 6. Push payload back to the browser
    logger.info(f"[WS] Pushing Plate: {plate_payload['plate_id']} (Intent: {plate_payload['intent']}, Skin: {plate_payload['strategy']['skin']}, Urgency: {attention_result.urgency_score})")
    await manager.send_personal_message(plate_payload, client_id)


# ---------------------------------------------------------------------------
# FastAPI WebSocket Router
# ---------------------------------------------------------------------------
chat_router = APIRouter()


@chat_router.websocket("/ws/chat")
async def websocket_chat_endpoint(websocket: WebSocket):
    """
    The primary C-OS WebSocket endpoint.

    Protocol:
      → Client sends: {"message": "Show me financials for Lane A"}
      ← Server sends: {"type": "MOUNT_PLATE", "plate_id": "FINANCE_CHART", ...}
    """
    # Generate a session-based client ID
    client_id = f"client_{id(websocket)}"

    await manager.connect(websocket, client_id)

    # Send welcome handshake
    await manager.send_personal_message({
        "type": "SYSTEM",
        "message": "AutoHaus C-OS v3.1 — Digital Chief of Staff connected.",
        "connected_clients": manager.active_count,
        "authority_state": "SOVEREIGN",
        "legacy_sync": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, client_id)

    try:
        while True:
            # Wait for inbound message from the React UI
            raw_data = await websocket.receive_text()

            try:
                data = json.loads(raw_data)
                user_message = data.get("message", "").strip()
            except json.JSONDecodeError:
                # Fallback: treat raw text as the message
                user_message = raw_data.strip()

            if not user_message:
                await manager.send_personal_message({
                    "type": "ERROR",
                    "message": "Empty command received. Please provide an instruction.",
                }, client_id)
                continue

            # Call the new message processing function
            await process_incoming_message(websocket, client_id, user_message)

    except WebSocketDisconnect:
        manager.disconnect(client_id)
        logger.info(f"[{client_id}] WebSocket closed cleanly.")
    except Exception as e:
        manager.disconnect(client_id)
        logger.error(f"[{client_id}] WebSocket error: {e}")
