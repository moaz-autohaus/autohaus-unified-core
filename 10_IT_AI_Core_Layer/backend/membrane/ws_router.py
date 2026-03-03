
import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from fastapi import WebSocket, WebSocketDisconnect
from membrane.session_context import SessionContext
from membrane.channel_selector import ChannelSelector
from membrane.translation_engine import TranslationEngine

# Setup logger
logger = logging.getLogger("autohaus.membrane.ws_router")

# Registry of active ephemeral membrane state
active_sessions: Dict[str, SessionContext] = {}
active_connections: Dict[str, WebSocket] = {}

class WebSocketRouter:
    """
    Orchestrator for active human-AI interactions.
    Handles connection lifecycle, heartbeat tracking, and JIT Plate routing.
    """
    
    def __init__(self):
        self.selector = ChannelSelector()
        self.translator = TranslationEngine()

    async def handle_connection(self, websocket: WebSocket, user_id: str):
        """Standard connection handler for the /ws/chat endpoint."""
        await websocket.accept()
        
        # 1. Initialize Session Context (calls SESSION_STARTED)
        session = SessionContext.create_session(user_id)
        session_id = session.session_id
        
        active_sessions[session_id] = session
        active_connections[session_id] = websocket
        
        logger.info(f"[WS] Connected: User={user_id} Session={session_id}")
        
        try:
            # 2. Connection Loop
            while True:
                # Receive messages (heartbeats or UI commands)
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Update activity timestamp for Channel Selector logic
                session.update_activity()
                
                if message.get("type") == "HEARTBEAT":
                    await websocket.send_json({"type": "HEARTBEAT_ACK", "timestamp": session.last_activity_at.isoformat()})
                
                # Handle UI-driven actions (e.g., resolving a plate)
                elif message.get("type") == "PLATE_ACTION":
                    await self._handle_ui_action(session, message.get("data", {}))
                    
        except WebSocketDisconnect:
            logger.info(f"[WS] Disconnected: Session={session_id}")
        except Exception as e:
            logger.error(f"[WS] Connection error for {session_id}: {e}")
        finally:
            # 3. Cleanup (calls SESSION_ENDED)
            self._cleanup_session(session_id)

    def _cleanup_session(self, session_id: str):
        session = active_sessions.pop(session_id, None)
        if session:
            session.end_session()
        active_connections.pop(session_id, None)

    async def _handle_ui_action(self, session: SessionContext, action_data: Dict[str, Any]):
        """Processes an action initiated by the human from a JIT Plate."""
        # This will eventually hand off to policy enforcer and then CIL spine
        logger.info(f"[WS] UI Action from {session.user_id}: {action_data.get('action')}")
        pass

    async def route_cil_event(self, cil_event: Dict[str, Any]):
        """
        Entry point for events arriving from the CIL spine (e.g., via background listener).
        Routes events to all eligible active sessions based on policy.
        """
        event_type = cil_event.get("event_type")
        payload_str = cil_event.get("payload", "{}")
        payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
        
        logger.debug(f"[WS] Routing CIL event: {event_type}")

        # Iterate over active human sessions
        for session_id, session in list(active_sessions.items()):
            # 1. Filter by Entity Scope
            target_id = cil_event.get("entity_id")
            if target_id and not session.is_in_scope(target_id):
                continue
                
            # 2. Check appropriate channel
            priority = cil_event.get("priority", "NORMAL")
            selection = self.selector.decide_channels(session, event_type, priority)
            
            if "WS" in selection.channels:
                # 3. Translate to UI Plate
                plate = self.translator.translate_to_plate(event_type, payload)
                if plate:
                    # 4. Push to UI
                    await self.push_message(session_id, "MOUNT_PLATE", plate.model_dump())

    async def push_message(self, session_id: str, msg_type: str, data: Any):
        """Sends a JSON message over the wire to a specific session."""
        websocket = active_connections.get(session_id)
        if websocket:
            try:
                await websocket.send_json({"type": msg_type, "data": data})
            except Exception as e:
                logger.error(f"[WS] Failed to push to {session_id}: {e}")
                # We don't cleanup here, let the receive loop catch the disconnect
