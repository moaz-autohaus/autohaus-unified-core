
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from membrane.session_context import SessionContext

# Setup logger
logger = logging.getLogger("autohaus.membrane.channel_selector")

class ChannelSelection(BaseModel):
    """Result of a channel selection decision."""
    channels: List[str] # ["WS", "SMS", "QUEUE"]
    reason: str

class ChannelSelector:
    """
    Determines delivery routing for CIL events headed to humans.
    Prioritizes WebSocket for active UI sessions, falling back to SMS for critical interrupts.
    """
    
    def decide_channels(self, session: SessionContext, event_type: str, priority: str = "NORMAL") -> ChannelSelection:
        """
        Main logic to decide HOW to reach the human.
        Based on session activity, event type, and priority.
        """
        # Calculate session activity (Heartbeat threshold: 30 seconds)
        time_since_activity = (datetime.now(timezone.utc) - session.last_activity_at).total_seconds()
        is_session_active = time_since_activity < 30.0
        
        logger.debug(f"[SELECTOR] Deciding channels for {event_type} (Priority: {priority}). Activity: {time_since_activity}s")

        # 1. Critical Interrupts / High Priority Alerts
        if priority == "HIGH" or event_type in ["MATERIAL_CONFLICT_DETECTED", "POLICY_BREACH_DETECTED"]:
            if is_session_active:
                # If they are in the UI, give them both for maximum presence
                return ChannelSelection(
                    channels=["WS", "SMS"], 
                    reason="Critical event detected. Session is active; pushing to UI and sending SMS alert."
                )
            else:
                # Fallback to SMS if they are away
                return ChannelSelection(
                    channels=["SMS"], 
                    reason="Critical event detected. Session is inactive; alerting via SMS."
                )

        # 2. Standard Session Logic
        if is_session_active:
            # Push to JIT UI via WebSocket
            return ChannelSelection(
                channels=["WS"], 
                reason="Session is active. Routing to JIT UI via WebSocket."
            )

        # 3. Inactive/Low Priority
        # Do not disturb. Stage the data in BigQuery (CIL already did this) 
        # and wait for them to log back in (WS sync on connect).
        return ChannelSelection(
            channels=["QUEUE"], 
            reason="Session is inactive. No immediate notification sent."
        )
