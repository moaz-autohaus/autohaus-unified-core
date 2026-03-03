
import json
import logging
import uuid
from typing import Dict, Any, Optional, List
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime, timezone

from membrane.session_context import SessionContext
from membrane.router_gateway import RouterGateway
# from pipeline.plate_generator_cil import PlateGeneratorCIL # Will be built in Step 6.6

logger = logging.getLogger("autohaus.membrane.ws_router")

class WSRouter:
    """
    Membrane Layer: Manages the bidirectional WebSocket nervous system.
    Tracks active sessions and injects context (active_entity) into the flow.
    """
    
    def __init__(self):
        self._connections: Dict[str, WebSocket] = {}
        self._sessions: Dict[str, SessionContext] = {}

    async def handle_connection(self, websocket: WebSocket, user_id: str):
        """Accepted loop for a new WebSocket."""
        await websocket.accept()
        
        # 1. Create Membrane Session
        session = SessionContext.create_session(user_id=user_id)
        connection_id = session.session_id
        
        self._connections[connection_id] = websocket
        self._sessions[connection_id] = session
        
        logger.info(f"[WS_ROUTER] session {connection_id} started for {user_id}")

        try:
            while True:
                raw_data = await websocket.receive_text()
                await self._process_frame(connection_id, raw_data)
        except WebSocketDisconnect:
            session.end_session()
            del self._connections[connection_id]
            del self._sessions[connection_id]
            logger.info(f"[WS_ROUTER] session {connection_id} ended.")
        except Exception as e:
            logger.error(f"[WS_ROUTER] Error in session {connection_id}: {e}")

    async def _process_frame(self, session_id: str, raw_data: str):
        """Main ingress loop for a session."""
        session = self._sessions[session_id]
        websocket = self._connections[session_id]
        
        try:
            data = json.loads(raw_data)
            message = data.get("message", "").strip()
            
            # Inject Active Entity if focused in UI
            active_entity = data.get("active_entity")
            if active_entity:
                session.active_entity = active_entity
            
            if not message:
                return

            # Call components (Bridge to CIL happens inside Gateways)
            router_gate = RouterGateway()
            decision = await router_gate.handle_input(session, message)
            
            # Deliver Decision
            await websocket.send_json(decision)
            
        except Exception as e:
            logger.error(f"[WS_ROUTER] Frame processing failed: {e}")
            await websocket.send_json({"status": "ERROR", "message": "An internal error occurred."})

    async def send_plate(self, session_id: str, plate_payload: Dict[str, Any]):
        """Pushes a JIT Plate to a specific session."""
        ws = self._connections.get(session_id)
        if ws:
            await ws.send_json({"type": "MOUNT_PLATE", **plate_payload})
