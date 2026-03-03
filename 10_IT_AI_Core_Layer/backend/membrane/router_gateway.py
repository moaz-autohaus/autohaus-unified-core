
import logging
import json
from typing import Optional, Dict, Any
from agents.router_agent import RouterAgent, RoutedIntent
from membrane.session_context import SessionContext
from membrane.policy_enforcer import PolicyEnforcer

logger = logging.getLogger("autohaus.membrane.router_gateway")

class RouterGateway:
    """
    Membrane Layer: The entryway for all human interaction.
    Handles session context injection, entity scope enforcement,
    and response delivery decisions.
    """
    
    def __init__(self):
        self.router = RouterAgent()
        self.enforcer = PolicyEnforcer()

    async def handle_input(self, session: SessionContext, user_input: str) -> Dict[str, Any]:
        """
        Receives raw human input and routes it through CIL after injecting context.
        Applies membrane-level enforcement before proceeding.
        """
        # 1. Inject Session Context (Membrane -> CIL)
        context_str = f"User: {session.user_id}, Role: {session.role}, Scope: {session.entity_scope}"
        
        # 2. Call CIL Classifier
        classification: RoutedIntent = await self.router.classify(user_input, context_str)
        
        # 3. Decision Logic: Check Entity Scope
        target = classification.target_entity
        if target and target != "ALL" and target != "CARBON_LLC":
            if not session.is_in_scope(target):
                logger.warning(f"[GATEWAY] Scope violation: {session.user_id} attempted to access {target}")
                
                # Emit enforcement event
                session.emit_event("HARD_STOP_ENFORCED", payload={
                    "reason": "ENTITY_SCOPE_VIOLATION",
                    "target_entity": target,
                    "action": classification.intent
                })
                
                return {
                    "status": "BLOCKED",
                    "reason": "SCOPE_VIOLATION",
                    "message": f"Security: Your role ({session.role}) does not have access to {target}."
                }

        # 4. Decision Logic: Handle Low Confidence
        if classification.confidence < 0.7:
            return {
                "status": "CLARIFY",
                "intent": classification.intent,
                "message": "I'm not exactly sure what you need. Could you clarify which vehicle or entity you're referring to?"
            }

        # 5. Delivery Decision
        # For now, return the classification to the caller (e.g. WebSocket handler)
        # In later steps, this will route to specific domain agents.
        return {
            "status": "ALLOWED",
            "classification": classification.to_dict(),
            "message": f"Routing to {classification.intent} domain..."
        }
