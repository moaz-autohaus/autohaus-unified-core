import json
import logging
import os
import uuid
from typing import Optional, Any
from datetime import datetime, timezone

import google.generativeai as genai
from pydantic import BaseModel

from database.policy_engine import get_policy
from database.bigquery_client import BigQueryClient

logger = logging.getLogger("autohaus.attention")

ATTENTION_SYSTEM_PROMPT_TEMPLATE = """You are the AutoHaus Attention Dispatcher.
Your job is to evaluate an operational event and determine:
1. The urgency score (1-10) of the event.
2. The optimal delivery channel for the CEO (Ahsin).

URGENCY SCALE:
{urgency_scale_text}

CHANNEL RULES:
- If Urgency >= {sms_threshold}: Route via "SMS" (Twilio). Ahsin needs a push notification right now.
- If Urgency < {sms_threshold}: Route via "WEBSOCKET". It will silently appear on his JIT Dashboard UI next time he looks.

OUTPUT FORMAT (STRICT JSON ONLY):
{{
  "urgency_score": 8,
  "route": "SMS",
  "synthesized_message": "A short, stark, professional summary of the event (max 2 sentences)."
}}
"""

class AttentionResult(BaseModel):
    urgency_score: int
    route: str
    synthesized_message: str
    advisory_only: bool = False

class AttentionDispatcher:
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        resolved_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not resolved_key:
            raise EnvironmentError("GEMINI_API_KEY is not set.")

        genai.configure(api_key=resolved_key)
        self.model_name = model_name
        self.bq_client = BigQueryClient()
        logger.info("Attention Dispatcher initialized with failover support.")

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

    def evaluate_event(
        self, 
        event_description: str,
        context_package: Optional[Any] = None
    ) -> AttentionResult:
        
        # Step 1: Read threshold from policy
        threshold_val = get_policy("AGENTS", "attention_sms_threshold")
        if threshold_val is None:
            logger.warning("[POLICY MISSING] AGENTS.attention_sms_threshold missing. Defaulting to 7.")
            sms_threshold = 7
            threshold_source = "DEFAULT"
        else:
            sms_threshold = int(threshold_val)
            threshold_source = "POLICY"

        # Step 2: Read urgency scale from policy
        urgency_scale_val = get_policy("AGENTS", "attention_urgency_scale")
        if urgency_scale_val is None:
            logger.warning("[POLICY MISSING] AGENTS.attention_urgency_scale missing. Using hardcoded fallback.")
            urgency_scale_dict = {
                "1-3": "Routine background noise (e.g. oil change complete, routine inventory move).",
                "4-6": "Standard operations needing later review (e.g. daily sales summary, normal delay).",
                "7-8": "Action requested but not critically time-sensitive (e.g. approve a $500 paint correction).",
                "9-10": "Critical anomalies / Blockers (e.g. Title rejected by KAMM, crash on Lane A, $50k wire bounced)."
            }
        else:
            urgency_scale_dict = json.loads(urgency_scale_val) if isinstance(urgency_scale_val, str) else urgency_scale_val

        # Format urgency scale text
        urgency_scale_text = "\\n".join([f"{k}: {v}" for k, v in urgency_scale_dict.items()])
        system_instruction = ATTENTION_SYSTEM_PROMPT_TEMPLATE.format(
            urgency_scale_text=urgency_scale_text,
            sms_threshold=sms_threshold
        )
        
        model = self._get_model(system_instruction)

        # Step 3: Require hydrated context
        advisory_only = False
        entity_ids = []
        prompt = ""
        
        if context_package is None:
            logger.warning("Significance detection running without hydration. Doctrine Rule 11 violation. Result is advisory only.")
            advisory_only = True
            prompt = f"RAW EVENT: {event_description}"
        else:
            entity_ids = context_package.resolved_entities if hasattr(context_package, 'resolved_entities') else []
            # Extract relevant context for LLM
            ctx_data = {
                "resolved_entities": entity_ids,
                "active_anomaly_flags": context_package.recent_anomaly_flags if hasattr(context_package, 'recent_anomaly_flags') else [],
                "open_questions": context_package.open_questions if hasattr(context_package, 'open_questions') else [],
                "active_proposals": context_package.active_proposals if hasattr(context_package, 'active_proposals') else []
            }
            prompt = f"CONTEXT: {json.dumps(ctx_data)}\n\nRAW EVENT: {event_description}"

        # Evaluate via LLM
        try:
            try:
                response = model.generate_content(prompt)
            except Exception as e_primary:
                logger.warning(f"Dispatcher Primary Model failed ({e_primary}). Attempting fallback...")
                fallback_model = genai.GenerativeModel(
                    model_name="gemini-2.5-pro",
                    system_instruction=system_instruction,
                    generation_config=genai.GenerationConfig(temperature=0.1, response_mime_type="application/json")
                )
                response = fallback_model.generate_content(prompt)
                
            data = json.loads(response.text.strip())
            urgency_score = data.get("urgency_score", 5)
            route = data.get("route", "WEBSOCKET")
            synthesized_message = data.get("synthesized_message", event_description)
            
        except Exception as e:
            logger.error(f"Attention Dispatcher Failed: {e}")
            urgency_score = 8
            route = "SMS"
            synthesized_message = f"SYSTEM ALL-CATCH: {event_description}"

        # Step 4: apply advisory_only suppression
        if advisory_only:
            logger.warning("Advisory only: Suppressing SMS routing for event.")
            route = "WEBSOCKET"

        # Step 5: Log routing decision durably
        now = datetime.now(timezone.utc).isoformat()
        event_row = {
            "event_id": str(uuid.uuid4()),
            "event_type": "ATTENTION_ROUTING_DECISION",
            "timestamp": now,
            "actor_type": "SYSTEM",
            "actor_id": "attention_dispatcher",
            "target_type": "SYSTEM",
            "target_id": "routing",
            "payload": json.dumps({
                "urgency_score": urgency_score,
                "threshold_used": sms_threshold,
                "threshold_source": threshold_source,
                "route_selected": route,
                "advisory_only": advisory_only,
                "context_hydrated": not advisory_only,
                "entity_ids": entity_ids
            }),
            "idempotency_key": None
        }
        
        if self.bq_client.client:
            try:
                self.bq_client.client.insert_rows_json("autohaus-infrastructure.autohaus_cil.cil_events", [event_row])
            except Exception as e:
                logger.error(f"Failed to log ATTENTION_ROUTING_DECISION: {e}")

        return AttentionResult(
            urgency_score=urgency_score,
            route=route,
            synthesized_message=synthesized_message,
            advisory_only=advisory_only
        )

if __name__ == "__main__":
    dispatcher = AttentionDispatcher()
    print("TEST 1 - No Hydration:")
    res1 = dispatcher.evaluate_event("The title clerk at KAMM LLC just got an email from the State. Title rejected.")
    print(res1)
