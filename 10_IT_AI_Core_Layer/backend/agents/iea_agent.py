import json
import logging
import os
from typing import Optional, Dict, Any

import google.generativeai as genai
from pydantic import BaseModel

logger = logging.getLogger("autohaus.iea")

IEA_SYSTEM_PROMPT = """You are the AutoHaus Input Enrichment Agent (IEA).
You operate the "Intelligent Membrane" sitting between messy human inputs and the strictly structured Central Intelligence Layer.

Your GOAL is to evaluate an incoming message and determine:
1. Is this a COMPLETE command that is ready to be routed to a specific system?
2. Or is this an INCOMPLETE command missing critical context (like a missing VIN, Lane ID, or cost amount)?

If INCOMPLETE:
You must return "status": "INCOMPLETE" and generate a single, low-friction, highly targeted "clarifying_question".
For example, if the human says "The subframe on the Porsche is rusted", you reply:
{"status": "INCOMPLETE", "clarifying_question": "I see the subframe issue on the Porsche. Do we have the VIN or the specific Repair Order number so I can attach this to the right record?"}

If COMPLETE:
You must return "status": "COMPLETE" and pass the full context along.

OUTPUT FORMAT (STRICT JSON ONLY):
{
  "status": "COMPLETE" | "INCOMPLETE",
  "clarifying_question": "The question to ask the user via SMS/Chat if incomplete",
  "extracted_entities": {
     "make": "Porsche",
     "issue": "rusted subframe"
  }
}
"""

class IEA_Result(BaseModel):
    status: str
    clarifying_question: str
    extracted_entities: Dict[str, Any]


class InputEnrichmentAgent:
    """
    Evaluates incoming human messages for completeness BEFORE hitting the main router.
    """
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        resolved_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not resolved_key:
            raise EnvironmentError("GEMINI_API_KEY is not set.")

        genai.configure(api_key=resolved_key)
        self._primary_model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=IEA_SYSTEM_PROMPT,
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
        self._fallback_model = genai.GenerativeModel(
            model_name="gemini-2.5-pro",
            system_instruction=IEA_SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                top_p=0.95,
                response_mime_type="application/json",
            )
        )
        logger.info("IEA Membrane initialized with failover support.")

    def evaluate(self, user_input: str, previous_context: Optional[dict] = None) -> IEA_Result:
        context_str = f"Previous Session Context: {json.dumps(previous_context)}\n" if previous_context else ""
        prompt = f"{context_str}NEW HUMAN INPUT: {user_input}"
        
        try:
            try:
                response = self._primary_model.generate_content(prompt)
            except Exception as e_primary:
                logger.warning(f"IEA Primary Model failed ({e_primary}). Attempting fallback...")
                try:
                    response = self._fallback_model.generate_content(prompt)
                except Exception as e_fallback:
                    logger.error(f"IEA Fallback Model failed ({e_fallback}). Force routing toCOMPLETE flag.")
                    return IEA_Result(
                        status="COMPLETE", 
                        clarifying_question="", 
                        extracted_entities={"error": "iea_llm_outage_bypassed"}
                    )
            
            data = json.loads(response.text.strip())
            return IEA_Result(
                status=data.get("status", "INCOMPLETE"),
                clarifying_question=data.get("clarifying_question", ""),
                extracted_entities=data.get("extracted_entities", {})
            )
        except Exception as e:
            logger.error(f"IEA Evaluation Failed: {e}")
            return IEA_Result(
                status="ERROR",
                clarifying_question="System error evaluating membrane logic.",
                extracted_entities={}
            )

if __name__ == "__main__":
    iea = InputEnrichmentAgent()
    print(iea.evaluate("The subframe on the white M4 looks pretty bad."))
