import json
import logging
import os
from typing import Optional

import google.generativeai as genai
from pydantic import BaseModel

logger = logging.getLogger("autohaus.attention")

ATTENTION_SYSTEM_PROMPT = """You are the AutoHaus Attention Dispatcher.
Your job is to evaluate an operational event and determine:
1. The urgency score (1-10) of the event.
2. The optimal delivery channel for the CEO (Ahsin).

URGENCY SCALE:
1-3: Routine background noise (e.g. oil change complete, routine inventory move).
4-6: Standard operations needing later review (e.g. daily sales summary, normal delay).
7-8: Action requested but not critically time-sensitive (e.g. approve a $500 paint correction).
9-10: Critical anomalies / Blockers (e.g. Title rejected by KAMM, crash on Lane A, $50k wire bounced).

CHANNEL RULES:
- If Urgency >= 7: Route via "SMS" (Twilio). Ahsin needs a push notification right now.
- If Urgency < 7: Route via "WEBSOCKET". It will silently appear on his JIT Dashboard UI next time he looks.

OUTPUT FORMAT (STRICT JSON ONLY):
{
  "urgency_score": 8,
  "route": "SMS" | "WEBSOCKET",
  "synthesized_message": "A short, stark, professional summary of the event (max 2 sentences). Example: 'Iowa DOT rejected the title for the 911. Mileage discrepancy.'",
  "metadata": {}
}
"""

class AttentionResult(BaseModel):
    urgency_score: int
    route: str
    synthesized_message: str

class AttentionDispatcher:
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        resolved_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not resolved_key:
            raise EnvironmentError("GEMINI_API_KEY is not set.")

        genai.configure(api_key=resolved_key)
        self._primary_model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=ATTENTION_SYSTEM_PROMPT,
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
            system_instruction=ATTENTION_SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                top_p=0.95,
                response_mime_type="application/json",
            )
        )
        logger.info("Attention Dispatcher initialized with failover support.")

    def evaluate_event(self, raw_event_description: str) -> AttentionResult:
        try:
            try:
                response = self._primary_model.generate_content(raw_event_description)
            except Exception as e_primary:
                logger.warning(f"Dispatcher Primary Model failed ({e_primary}). Attempting fallback...")
                try:
                    response = self._fallback_model.generate_content(raw_event_description)
                except Exception as e_fallback:
                    logger.error(f"Dispatcher Fallback Model failed ({e_fallback}). Force returning emergency score.")
                    return AttentionResult(
                        urgency_score=9,  # High urgency to guarantee visibility of outage
                        route="SMS",
                        synthesized_message=f"SYSTEM OUTAGE. AI Models unreachable. Raw Event: {raw_event_description[:100]}"
                    )
            
            data = json.loads(response.text.strip())
            return AttentionResult(
                urgency_score=data.get("urgency_score", 5),
                route=data.get("route", "WEBSOCKET"),
                synthesized_message=data.get("synthesized_message", raw_event_description)
            )
        except Exception as e:
            logger.error(f"Attention Dispatcher Failed: {e}")
            return AttentionResult(
                urgency_score=8,  # Default high on error to ensure Delivery
                route="SMS",
                synthesized_message=f"SYSTEM ALL-CATCH: {raw_event_description}"
            )

if __name__ == "__main__":
    dispatcher = AttentionDispatcher()
    print("TEST 1 - KAMM Error:")
    res1 = dispatcher.evaluate_event("The title clerk at KAMM LLC just got an email from the State. Title rejected for the Toyota due to unsigned odometer disclosure.")
    print(res1)
    
    print("\nTEST 2 - Routine Oil Change:")
    res2 = dispatcher.evaluate_event("Service Lane A finished the oil change and rotate on the Audi X3.")
    print(res2)
