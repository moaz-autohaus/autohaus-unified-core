
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
        Yields an EnforcementOutcome and emits enforcement events to cil_events.
        """
        logger.info(f"[ENFORCER] Evaluating '{action_type}' for user {session.user_id} on target {target_id}")

        # 1. Role-based Permission Check (Static Boundary)
        # Based on CIL_MASTER_BLUEPRINT v2.0
        role_permissions = {
            "SOVEREIGN": ["ADMIN_OVERRIDE", "POLICY_WRITE", "CIL_RESET", "PIPELINE_FREEZE", 
                          "VALIDATE_CLAIM", "ENTITY_RESOLVE", "FORCE_APPLY_FIELD", 
                          "CREATE_OPEN_QUESTION", "UPLOAD_DOC", "VIEW_PLATE", "CREATE_CLAIM_STUB"],
            "STANDARD": ["VALIDATE_CLAIM", "ENTITY_RESOLVE", "FORCE_APPLY_FIELD", 
                         "CREATE_OPEN_QUESTION", "UPLOAD_DOC", "VIEW_PLATE", "CREATE_CLAIM_STUB"],
            "FIELD": ["UPLOAD_DOC", "VIEW_PLATE", "CREATE_CLAIM_STUB"]
        }
        
        allowed_actions = role_permissions.get(session.role, [])
        if action_type not in allowed_actions and "ADMIN_OVERRIDE" not in allowed_actions:
             outcome = EnforcementOutcome(
                 status="STOP", 
                 reason=f"Role '{session.role}' lacks explicit permission for '{action_type}'"
             )
             self._emit_enforcement_event(session, "HARD_STOP_ENFORCED", outcome, action_type, target_id)
             return outcome

        # 2. Entity Scope Check (Dynamic Boundary)
        if target_id and not session.is_in_scope(target_id):
            outcome = EnforcementOutcome(
                status="STOP", 
                reason=f"Entity '{target_id}' is outside the authorized scope for this session"
            )
            self._emit_enforcement_event(session, "HARD_STOP_ENFORCED", outcome, action_type, target_id)
            return outcome

        # 3. Interrogate CIL Truths for Active Blocks (HARD STOPs)
        if target_id:
            active_blocks = await self._check_active_blocks(target_id)
            if active_blocks:
                # If there are active blocks, strictly STOP for non-SOVEREIGN
                if session.role != "SOVEREIGN":
                    outcome = EnforcementOutcome(
                        status="STOP", 
                        reason=f"Active HARD STOP on entity {target_id}: {active_blocks[0]['reason']}",
                        block_id=active_blocks[0]['block_id']
                    )
                    self._emit_enforcement_event(session, "HARD_STOP_ENFORCED", outcome, action_type, target_id)
                    return outcome
                else:
                    logger.warning(f"[ENFORCER] SOVEREIGN user {session.user_id} proceeding despite active block: {active_blocks[0]['reason']}")

        # 4. Check for APPROVAL GATES
        # Example logic: if a standard user tries to 'FORCE_APPLY_FIELD', trigger a gate
        if action_type == "FORCE_APPLY_FIELD" and session.role == "STANDARD":
            gate_id = str(uuid.uuid4())
            outcome = EnforcementOutcome(
                status="GATE",
                reason="High-authority action requires SOVEREIGN approval gate.",
                block_id=gate_id
            )
            self._emit_enforcement_event(session, "ENRICHMENT_PROPOSED", outcome, action_type, target_id)
            session.pending_approvals.append(gate_id)
            return outcome

        # Default: ALLOWED
        return EnforcementOutcome(status="ALLOWED")

    async def _check_active_blocks(self, entity_id: str) -> List[Dict[str, Any]]:
        """Queries the PENDING_VERIFICATION_QUEUE and COMPLIANCE_TIMELINE projections."""
        if not self.bq.client:
            return []
            
        # Interrogate CIL projections (Canonical Reference Section 5)
        query = f"""
            SELECT 'CONFLICT' as type, claim_id as block_id, target_field as reason
            FROM `autohaus-infrastructure.autohaus_cil.pending_verification_queue`
            WHERE target_id = @entity_id AND truth_status = 'CONFLICT'
            UNION ALL
            SELECT 'BREACH' as type, event_id as block_id, event_type as reason
            FROM `autohaus-infrastructure.autohaus_cil.compliance_timeline`
            WHERE target_id = @entity_id AND event_type = 'THRESHOLD_BREACHED'
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("entity_id", "STRING", entity_id)]
        )
        
        try:
            results = list(self.bq.client.query(query, job_config=job_config).result())
            return [{"type": r.type, "block_id": r.block_id, "reason": f"{r.type}: {r.reason}"} for r in results]
        except Exception as e:
            # Projections might be empty/table not found early in build
            logger.debug(f"[ENFORCER] Truth lookup skipped or failed for {entity_id}: {e}")
            return []

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
