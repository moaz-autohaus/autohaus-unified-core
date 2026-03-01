import json
import logging
import os
from typing import Optional, Dict, Any

import google.generativeai as genai
from pydantic import BaseModel

from database.policy_engine import get_policy
from database.open_questions import create_question

logger = logging.getLogger("autohaus.iea")

DOMAIN_CLASSIFIER_PROMPT = """Classify the following user input into one of these operational domains:
INVENTORY, FINANCE, LOGISTICS, SERVICE, CRM, COMPLIANCE.
Reply with ONLY the domain name in ALL CAPS. If unsure, reply CRM.
"""

IEA_SYSTEM_PROMPT_TEMPLATE = """You are the AutoHaus Input Enrichment Agent (IEA).
You operate the "Intelligent Membrane" sitting between messy human inputs and the strictly structured Central Intelligence Layer.

DOMAIN: {domain}

Your GOAL is to evaluate an incoming message and determine:
1. Is this a COMPLETE command that is ready to be routed to a specific system?
2. Or is this an INCOMPLETE command missing critical context?

REQUIRED FIELDS FOR THIS DOMAIN: {required_fields}
KNOWN/RESOLVED ENTITIES (DO NOT ask the user for these if they are already known): {resolved_entities}

If any required field is missing and not present in the known entities, the command is INCOMPLETE.

If INCOMPLETE:
You must return "status": "INCOMPLETE" and generate a single, low-friction, highly targeted "clarifying_question".
You MUST have a confidence score below {confidence_threshold} to mark it INCOMPLETE if there's ambiguity. 

If COMPLETE (all required fields present or confidence >= {confidence_threshold}):
You must return "status": "COMPLETE" and pass the full context along.

OUTPUT FORMAT (STRICT JSON ONLY):
{{
  "status": "COMPLETE" | "INCOMPLETE",
  "confidence": 0.9,
  "clarifying_question": "The question to ask the user via SMS/Chat if incomplete. Provide empty string if complete.",
  "extracted_entities": {{
     "make": "Porsche",
     "issue": "rusted subframe"
  }}
}}
"""

class IEA_Result(BaseModel):
    status: str
    clarifying_question: str
    extracted_entities: Dict[str, Any]
    question_id: Optional[str] = None
    existing_question_id: Optional[str] = None


class InputEnrichmentAgent:
    """
    Evaluates incoming human messages for completeness BEFORE hitting the main router.
    """
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash", bq_client=None):
        resolved_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not resolved_key:
            raise EnvironmentError("GEMINI_API_KEY is not set.")

        genai.configure(api_key=resolved_key)
        self.model_name = model_name
        self.bq_client = bq_client
        logger.info("IEA Membrane initialized with failover support.")

    def _get_model(self, system_instruction: str) -> genai.GenerativeModel:
        return genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_instruction,
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                top_p=0.95,
                response_mime_type="application/json",
            ),
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        )

    def _classify_domain(self, user_input: str) -> str:
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=DOMAIN_CLASSIFIER_PROMPT,
            generation_config=genai.GenerationConfig(temperature=0.1, response_mime_type="text/plain")
        )
        try:
            resp = model.generate_content(f"INPUT: {user_input}")
            domain = resp.text.strip().upper()
            if domain not in ["INVENTORY", "FINANCE", "LOGISTICS", "SERVICE", "CRM", "COMPLIANCE"]:
                domain = "CRM"
            return domain
        except Exception as e:
            logger.warning(f"Domain classification failed: {e}")
            return "CRM"

    def evaluate(self, user_input: str, previous_context: Optional[list] = None, context_package: Optional[Any] = None) -> IEA_Result:
        
        # Step 1: Pre-classify domain
        domain = self._classify_domain(user_input)
        
        # Query policy for required fields
        required_fields_val = get_policy("AGENTS", f"iea_required_fields_{domain}")
        if required_fields_val is None:
            logger.info(f"Required fields for {domain} not found, falling back to CRM.")
            required_fields_val = get_policy("AGENTS", "iea_required_fields_CRM")
        
        try:
            required_fields = json.loads(required_fields_val) if isinstance(required_fields_val, str) else (required_fields_val or ["contact_identifier"])
        except:
            required_fields = ["contact_identifier"]

        # Step 2: Query policy for confidence threshold
        conf_val = get_policy("AGENTS", "iea_confidence_threshold")
        if conf_val is None:
            logger.warning("[POLICY MISSING] AGENTS::iea_confidence_threshold missing. Defaulting to 0.7.")
            confidence_threshold = 0.7
        else:
            confidence_threshold = float(conf_val)

        # Step 3: Handle hydrated context
        resolved_entities = []
        if context_package:
            resolved_entities = context_package.resolved_entities if hasattr(context_package, 'resolved_entities') else []
            
            # Check existing open questions for matching topic (simple heuristic using keyword overlap)
            open_questions = context_package.open_questions if hasattr(context_package, 'open_questions') else []
            words_in_input = set(user_input.lower().split())
            for q in open_questions:
                q_content = q.get('content', '').lower()
                q_words = set(q_content.split())
                overlap = len(words_in_input.intersection(q_words))
                if overlap >= 3 or (len(words_in_input) > 0 and overlap / len(words_in_input) > 0.5):
                    logger.info(f"Matched existing open question {q.get('question_id')} to input.")
                    return IEA_Result(
                        status="INCOMPLETE",
                        clarifying_question="This question is already open. Waiting for resolution.",
                        extracted_entities={},
                        existing_question_id=q.get("question_id")
                    )

        sys_prompt = IEA_SYSTEM_PROMPT_TEMPLATE.format(
            domain=domain,
            required_fields=json.dumps(required_fields),
            resolved_entities=json.dumps(resolved_entities),
            confidence_threshold=confidence_threshold
        )
        
        prompt = f"Previous Context: {json.dumps(previous_context)}\n\nNEW HUMAN INPUT: {user_input}"
        model = self._get_model(sys_prompt)
        
        try:
            try:
                response = model.generate_content(prompt)
            except Exception as e_primary:
                logger.warning(f"IEA Primary Model failed ({e_primary}). Attempting fallback...")
                fallback_model = genai.GenerativeModel(
                    model_name="gemini-2.5-pro",
                    system_instruction=sys_prompt,
                    generation_config=genai.GenerationConfig(temperature=0.1, response_mime_type="application/json")
                )
                response = fallback_model.generate_content(prompt)
                
            data = json.loads(response.text.strip())
            
            # Apply confidence threshold strictly
            status = data.get("status", "INCOMPLETE")
            conf = data.get("confidence", 1.0)
            if status == "COMPLETE" and conf < confidence_threshold:
                status = "INCOMPLETE"
                
            res = IEA_Result(
                status=status,
                clarifying_question=data.get("clarifying_question", ""),
                extracted_entities=data.get("extracted_entities", {})
            )
            
            # Step 4: Routing to create_question if INCOMPLETE
            if res.status == "INCOMPLETE" and res.clarifying_question:
                q = create_question(
                    content=res.clarifying_question,
                    source_type="IEA",
                    source_id="conversation_turn_id", # Real integration should pass actual context id
                    owner_role="STANDARD", 
                    dependency_list=["current_conversation_turn"],
                    lineage_pointer={
                        "source_type": "IEA",
                        "source_id": "conversation_turn_id",
                        "conflict_outcome": None,
                        "assertion_type": None
                    },
                    bq_client=self.bq_client
                )
                res.question_id = q.question_id
                
            return res
            
        except Exception as e:
            logger.error(f"IEA Evaluation Failed: {e}")
            return IEA_Result(
                status="ERROR",
                clarifying_question="System error evaluating membrane logic.",
                extracted_entities={}
            )

if __name__ == "__main__":
    iea = InputEnrichmentAgent()
    print(iea.evaluate("Update the price for the Porsche"))
