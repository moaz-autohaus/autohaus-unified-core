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
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Import the Agentic Router from Module 2
from agents.router_agent import RouterAgent, RoutedIntent

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
# JIT Plate Builder
# ---------------------------------------------------------------------------
def build_plate_payload(routed: RoutedIntent) -> dict:
    """
    Translate a RoutedIntent into a JIT Plate mount command for the React UI.

    The React <PlateHydrator /> component listens for these payloads and
    dynamically imports and renders the correct visualization component.
    """
    plate_id = PLATE_MAP.get(routed.intent, "CHAT_RESPONSE")

    # If confidence is low, override to ambiguity resolution
    if routed.confidence < 0.7 and routed.intent != "UNKNOWN":
        plate_id = "AMBIGUITY_RESOLUTION"

    payload = {
        "type": "MOUNT_PLATE",
        "plate_id": plate_id,
        "intent": routed.intent,
        "confidence": routed.confidence,
        "entities": routed.entities,
        "target_entity": routed.target_entity,
        "suggested_action": routed.suggested_action,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": [],  # Placeholder: hydrated with BigQuery data in future modules
    }

    return payload


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

            logger.info(f"[{client_id}] Received: {user_message[:80]}")

            # ── STEP 1: Classify intent via the Agentic Router ──
            router = _get_router()
            routed_intent = router.classify(user_message)

            # ── STEP 2: Build the JIT Plate payload ──
            plate_payload = build_plate_payload(routed_intent)

            # ── STEP 3: Push the Plate to the client ──
            await manager.send_personal_message(plate_payload, client_id)

            logger.info(
                f"[{client_id}] Pushed plate: {plate_payload['plate_id']} "
                f"(confidence: {routed_intent.confidence})"
            )

    except WebSocketDisconnect:
        manager.disconnect(client_id)
        logger.info(f"[{client_id}] WebSocket closed cleanly.")
    except Exception as e:
        manager.disconnect(client_id)
        logger.error(f"[{client_id}] WebSocket error: {e}")
