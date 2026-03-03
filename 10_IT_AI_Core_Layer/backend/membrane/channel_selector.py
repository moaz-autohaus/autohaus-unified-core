
import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import uuid

from agents.attention_dispatcher import AttentionResult
from membrane.session_context import SessionContext
from database.policy_engine import get_policy
# from membrane.ws_router import WSRouter # Will be built in Step 5

logger = logging.getLogger("autohaus.membrane.channel_selector")

class ChannelSelector:
    """
    Membrane Layer: Decides which channel delivers a CIL conclusion.
    Orchestrates delivery via SMS, WebSocket, or both.
    """
    
    def __init__(self):
        # self.ws_router = WSRouter()
        pass

    async def dispatch(self, result: AttentionResult, session: Optional[SessionContext] = None, event_id: Optional[str] = None):
        """
        Receives evaluation from CIL and session context from Membrane.
        Determines and executes delivery.
        """
        # Step 1: Read Routing Thresholds from Policy
        sms_threshold = int(get_policy("AGENTS", "attention_sms_threshold") or 7)
        
        # Step 2: Determine Channel based on Policy Domain CHANNELS
        # (Simplified logic for Step 6.2 - will expand as spokes are built)
        selected_channels = []
        
        if result.urgency_score >= sms_threshold:
            selected_channels.append("SMS")
        
        # If there is an active session, always include WebSocket for dashboard
        if session:
            selected_channels.append("WEBSOCKET")
        
        # Advisory suppression
        if result.advisory_only and "SMS" in selected_channels:
            logger.info("[SELECTOR] Advisory only: Suppressing SMS.")
            selected_channels.remove("SMS")
            if "WEBSOCKET" not in selected_channels:
                selected_channels.append("WEBSOCKET")

        # Step 3: Execute Dispatch
        for channel in selected_channels:
            await self._deliver(channel, result, session, event_id)

    async def _deliver(self, channel: str, result: AttentionResult, session: Optional[SessionContext], trigger_event_id: str):
        """Standardized delivery wrapper."""
        logger.info(f"[SELECTOR] Delivering message via {channel}: {result.synthesized_message[:50]}...")
        
        if channel == "SMS":
            await self._dispatch_sms(session.user_id if session else "CEO_AHSIN", result.synthesized_message, trigger_event_id)
        elif channel == "WEBSOCKET":
            if session:
                await self._dispatch_websocket(session.session_id, result.synthesized_message, trigger_event_id)
            else:
                logger.debug("[SELECTOR] No active session for WebSocket delivery.")

    async def _dispatch_sms(self, user_id: str, message: str, correlation_id: str):
        """Calls Twilio and logs OUTBOUND_SMS_SENT."""
        # TODO: Wire to twilio_webhooks.py in Step 6.6
        logger.info(f"[SMS] Simulating dispatch to {user_id}: {message}")
        
        # Log to cil_events (Canonical Step 3 Requirement)
        self._log_delivery_event("OUTBOUND_SMS_SENT", user_id, message, correlation_id)

    async def _dispatch_websocket(self, session_id: str, message: str, correlation_id: str):
        """Calls WSRouter and logs MOUNT_PLATE delivery."""
        logger.info(f"[WS] Simulating MOUNT_PLATE to {session_id}")
        # self.ws_router.send_plate(session_id, {"type": "ANOMALY_ALERT", "message": message})
        
        # Log to cil_events
        self._log_delivery_event("WEBSOCKET_PLATE_MOUNTED", session_id, message, correlation_id)

    def _log_delivery_event(self, event_type: str, target: str, message: str, correlation_id: str):
        """Membrane logs the enforcement/delivery action."""
        from database.bigquery_client import BigQueryClient
        bq = BigQueryClient()
        if not bq.client: return

        event_row = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor_type": "SYSTEM",
            "actor_id": "channel_selector",
            "target_type": "SESSION" if "WEBSOCKET" in event_type else "PERSON",
            "target_id": target,
            "payload": json.dumps({
                "message": message,
                "correlation_id": correlation_id
            })
        }
        try:
            bq.client.insert_rows_json("autohaus-infrastructure.autohaus_cil.cil_events", [event_row])
        except Exception as e:
            logger.error(f"Failed to log {event_type}: {e}")
