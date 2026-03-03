
import logging
from typing import Optional, Dict, Any

from agents.iea_agent import InputEnrichmentAgent, IEA_Result
from membrane.session_context import SessionContext
from database.open_questions import create_question

logger = logging.getLogger("autohaus.membrane.iea_bridge")

class IEARouter:
    """
    Membrane Layer: Routes clarifying questions to the correct roles.
    Wraps the CIL IEA evaluator and adds behavioral enforcement.
    """
    
    def __init__(self):
        self.iea = InputEnrichmentAgent()

    async def process_and_route(self, session: SessionContext, user_input: str) -> Dict[str, Any]:
        """
        Calls CIL evaluation and performs role-based routing if incomplete.
        """
        # 1. Call CIL Evaluator (Pure Intelligence)
        result: IEA_Result = await self.iea.evaluate(user_input)
        
        # 2. Decision Logic: Question Routing
        if result.status == "INCOMPLETE":
            # Determine Owner Role based on session and domain
            # Rule: Defaults to STANDARD, but if session is FIELD, use FIELD if appropriate.
            # For now, following Step 6 requirement: "routing to correct owner role".
            owner_role = session.role
            
            logger.info(f"[IEA_BRIDGE] Routing clarifying question to {owner_role}: {result.clarifying_question}")
            
            # 3. Create CIL Question (Side-effect triggered by Membrane)
            q = create_question(
                content=result.clarifying_question,
                source_type="IEA",
                source_id=f"session_{session.session_id}",
                owner_role=owner_role,
                dependency_list=["current_turn"],
                lineage_pointer={
                    "source_type": "IEA_MEMBRANE",
                    "actor_id": session.user_id,
                    "session_id": session.session_id
                }
            )
            
            # Emit Event via Session (Canonical Requirement)
            session.emit_event("QUESTION_CREATED", payload={
                "question_id": q.question_id,
                "text": result.clarifying_question,
                "owner_role": owner_role
            })
            
            return {
                "status": "QUESTION_REQUIRED",
                "question_id": q.question_id,
                "message": result.clarifying_question
            }

        return {
            "status": "PROCEED",
            "extracted": result.extracted_entities
        }
