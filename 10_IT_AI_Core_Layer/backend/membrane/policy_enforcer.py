
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from membrane.session_context import SessionContext
from google.cloud import bigquery

# Setup logger
logger = logging.getLogger("autohaus.membrane.policy_enforcer")

class EnforcementOutcome(BaseModel):
    """Result of a policy enforcement check."""
    status: str # ALLOWED | GATE | STOP
    reason: Optional[str] = None
    block_id: Optional[str] = None

class PolicyEnforcer:
    """
    Exclusive layer for enforcement logic (HARD STOPs, APPROVAL GATES).
    This component consumes CIL truths but MUST NOT evaluate or create policy.
    """
    def __init__(self, bq_client=None):
        from database.bigquery_client import BigQueryClient
        self.bq = bq_client or BigQueryClient()

    async def enforce_action(self, session: SessionContext, action_type: str, target_id: Optional[str] = None) -> EnforcementOutcome:
        """
        Main entry point for enforcement.
        Membrane side: Handles the STOP UI and session management.
        """
        from pipeline.policy_engine_cil import PolicyEngineCIL
        cil_engine = PolicyEngineCIL(self.bq)

        logger.info(f"[ENFORCER] Evaluating '{action_type}' for user {session.user_id}")

        # 1. Role-based Permission Check
        role_permissions = {
            "SOVEREIGN": ["*"],
            "STANDARD": ["VALIDATE_CLAIM", "ENTITY_RESOLVE", "FORCE_APPLY_FIELD", "UPLOAD_DOC"],
            "FIELD": ["UPLOAD_DOC", "VIEW_PLATE"]
        }
        
        allowed_actions = role_permissions.get(session.role, [])
        if "*" not in allowed_actions and action_type not in allowed_actions:
             outcome = EnforcementOutcome(status="STOP", reason=f"Access Denied: Role {session.role} cannot perform {action_type}")
             self._emit_enforcement_event(session, "HARD_STOP_ENFORCED", outcome, action_type, target_id)
             return outcome

        # 2. Entity Scope Check
        if target_id and not session.is_in_scope(target_id):
            outcome = EnforcementOutcome(status="STOP", reason=f"Access Denied: {target_id} is out of scope.")
            self._emit_enforcement_event(session, "HARD_STOP_ENFORCED", outcome, action_type, target_id)
            return outcome

        # 3. Interrogate CIL Truths for Active Blocks
        if target_id:
            breaches = await cil_engine.detect_breaches(target_id)
            if breaches:
                # Update Session State (Hard Stop management)
                for b in breaches:
                    if b['block_id'] not in session.active_hard_stops:
                        session.active_hard_stops.append(b['block_id'])

                if session.role != "SOVEREIGN":
                    outcome = EnforcementOutcome(
                        status="STOP",
                        reason=f"HARD STOP: {breaches[0]['reason']}",
                        block_id=breaches[0]['block_id']
                    )
                    self._emit_enforcement_event(session, "HARD_STOP_ENFORCED", outcome, action_type, target_id)
                    return outcome
                else:
                    logger.warning(f"[ENFORCER] SOVEREIGN user {session.user_id} proceeding despite active block: {breaches[0]['reason']}")

        # 4. Check for APPROVAL GATES
        if action_type == "FORCE_APPLY_FIELD" and session.role == "STANDARD":
            gate_id = str(uuid.uuid4())
            outcome = EnforcementOutcome(status="GATE", reason="Soverign approval required.", block_id=gate_id)
            self._emit_enforcement_event(session, "ENRICHMENT_PROPOSED", outcome, action_type, target_id)
            session.pending_approvals.append(gate_id)
            return outcome

        return EnforcementOutcome(status="ALLOWED")

    def _emit_enforcement_event(self, session: SessionContext, event_type: str, outcome: EnforcementOutcome, action: str, target: Optional[str]):
        """Emits an enforcement logging event to the cil_events spine."""
        payload = {
            "action_attempted": action,
            "target_id": target,
            "outcome_status": outcome.status,
            "reason": outcome.reason,
            "block_id": outcome.block_id
        }
        session.emit_event(event_type, payload)
