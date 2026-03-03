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

    async def evaluate_event(
        self, 
        event_description: str,
        context_package: Optional[Any] = None
    ) -> AttentionResult:
        """
        CIL Layer: Evaluates event significance and synthesizes messages.
        Does NOT decide the channel; that is a Membrane activity.
        """
        # Read urgency scale from policy
        urgency_scale_val = get_policy("AGENTS", "attention_urgency_scale")
        if urgency_scale_val is None:
            urgency_scale_dict = {
                "1-3": "Routine background noise.",
                "4-6": "Standard operations needing review.",
                "7-8": "Action requested, not critical.",
                "9-10": "Critical anomalies / Blockers."
            }
        else:
            urgency_scale_dict = json.loads(urgency_scale_val) if isinstance(urgency_scale_val, str) else urgency_scale_val

        urgency_scale_text = "\\n".join([f"{k}: {v}" for k, v in urgency_scale_dict.items()])
        
        # Simplified system prompt (pure evaluation)
        system_instruction = f"""You are the AutoHaus Attention Dispatcher.
Evaluate an operational event and determine its urgency (1-10).
URGENCY SCALE:
{urgency_scale_text}

OUTPUT FORMAT (JSON):
{{
  "urgency_score": 8,
  "synthesized_message": "A short, professional summary."
}}"""
        
        model = self._get_model(system_instruction)

        advisory_only = False
        entity_ids = []
        if context_package is None:
            advisory_only = True
            prompt = f"RAW EVENT: {event_description}"
        else:
            entity_ids = context_package.resolved_entities if hasattr(context_package, 'resolved_entities') else []
            ctx_data = {
                "resolved_entities": entity_ids,
                "active_flags": context_package.recent_anomaly_flags if hasattr(context_package, 'recent_anomaly_flags') else []
            }
            prompt = f"CONTEXT: {json.dumps(ctx_data)}\n\nRAW EVENT: {event_description}"

        try:
            response = await model.generate_content_async(prompt)
            data = json.loads(response.text.strip())
            urgency_score = int(data.get("urgency_score", 5))
            synthesized_message = data.get("synthesized_message", event_description)
        except Exception as e:
            logger.error(f"Attention Dispatcher (CIL) Failed: {e}")
            urgency_score = 8
            synthesized_message = f"SYSTEM EVAL ERROR: {event_description}"

        # CIL Logs the evaluation event
        event_row = {
            "event_id": str(uuid.uuid4()),
            "event_type": "ATTENTION_EVALUATED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor_type": "SYSTEM",
            "actor_id": "attention_dispatcher",
            "target_type": "SYSTEM",
            "target_id": "routing_pre_gate",
            "payload": json.dumps({
                "urgency_score": urgency_score,
                "synthesized": synthesized_message,
                "entity_ids": entity_ids
            })
        }
        
        if self.bq_client.client:
            try:
                self.bq_client.client.insert_rows_json("autohaus-infrastructure.autohaus_cil.cil_events", [event_row])
            except Exception as e:
                logger.error(f"Failed to log ATTENTION_EVALUATED: {e}")

        return AttentionResult(
            urgency_score=urgency_score,
            route="CIL_ONLY", # Placeholder; Membrane chooses.
            synthesized_message=synthesized_message,
            advisory_only=advisory_only
        )

if __name__ == "__main__":
    dispatcher = AttentionDispatcher()
    print("TEST 1 - No Hydration:")
    res1 = dispatcher.evaluate_event("The title clerk at KAMM LLC just got an email from the State. Title rejected.")
    print(res1)
