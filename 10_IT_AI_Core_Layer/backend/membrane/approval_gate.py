
import logging
from typing import Optional, Dict, Any, List
from membrane.session_context import SessionContext
from membrane.channel_selector import ChannelSelector
from pipeline.hitl_service import validate, apply, HitlStatus
from agents.attention_dispatcher import AttentionResult

logger = logging.getLogger("autohaus.membrane.approval_gate")

class ApprovalGate:
    """
    Membrane Layer: Manages the interaction between HITL proposals and active users.
    Ensures high-risk actions are approved via the correct channel/UI.
    """
    
    def __init__(self):
        self.selector = ChannelSelector()

    async def notify_pending_proposal(self, session: SessionContext, proposal_id: str, summary: str):
        """
        Informs the user that an action requires their approval.
        Updates session state and dispatches across channels.
        """
        # 1. Update Session Memory
        if proposal_id not in session.pending_approvals:
            session.pending_approvals.append(proposal_id)
            logger.info(f"[GATE] Added pending approval {proposal_id} to session {session.session_id}")

        # 2. Dispatch Notification
        # We wrap this as an AttentionResult so ChannelSelector can handle it
        notif = AttentionResult(
            urgency_score=8, # Approvals are generally high-urgency
            route="BOTH",
            synthesized_message=f"APPROVAL REQUIRED: {summary}"
        )
        
        await self.selector.dispatch(notif, session, event_id=proposal_id)

    async def process_decision(self, session: SessionContext, proposal_id: str, decision: str, bq_client):
        """
        Receives a 'REJECT' or 'APPROVE' decision from the membrane (WebSocket/Chat).
        """
        if proposal_id not in session.pending_approvals:
            return {"status": "ERROR", "message": "Proposal not pending for this session."}

        if decision == "APPROVE":
            # Call CIL Apply
            result = await apply(bq_client, proposal_id)
            if result.get("status") == "APPLIED":
                session.pending_approvals.remove(proposal_id)
                session.emit_event("APPROVAL_GRANTED", payload={"proposal_id": proposal_id})
                return {"status": "SUCCESS", "message": "Action applied successfully."}
            else:
                return {"status": "ERROR", "message": result.get("reason", "Failed to apply.")}
        
        elif decision == "REJECT":
            # Logic to mark hitl_event as REJECTED in CIL
            # (Requires a status update helper in hitl_service)
            session.pending_approvals.remove(proposal_id)
            session.emit_event("APPROVAL_REJECTED", payload={"proposal_id": proposal_id})
            return {"status": "SUCCESS", "message": "Proposal rejected."}

        return {"status": "ERROR", "message": "Invalid decision."}
