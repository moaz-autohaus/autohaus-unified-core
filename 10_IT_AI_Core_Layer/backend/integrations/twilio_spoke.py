import os
import json
import logging
import uuid
from typing import Optional, Dict, Any
from twilio.rest import Client
from database.policy_engine import get_policy
from database.bigquery_client import BigQueryClient

logger = logging.getLogger("autohaus.twilio_spoke")

class TwilioSpoke:
    def __init__(self, bq_client=None):
        self.bq = bq_client or BigQueryClient()
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        self.client = None
        
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            logger.warning("[TWILIO] Missing credentials. SMS will be simulated.")

    async def send_sms(self, to_number: str, message: str, purpose: str = "CIL_OPS") -> Dict[str, Any]:
        """
        Send an SMS using a policy-governed number based on purpose.
        """
        # Resolve from number based on purpose
        from_number = get_policy("TWILIO", f"{purpose}_NUMBER")
        
        if not from_number:
            # Fallback to env if policy missing
            from_number = os.environ.get("TWILIO_PHONE_NUMBER")
            
        if not from_number:
            return {"status": "failed", "error": f"No phone number found for purpose {purpose}"}

        logger.info(f"[TWILIO] Sending {purpose} SMS to {to_number} from {from_number}")

        if not self.client:
            logger.info(f"[SIMULATED SMS] From: {from_number}, To: {to_number}, Body: {message}")
            return {"status": "simulated", "message_sid": f"SM{uuid.uuid4().hex}"}

        try:
            msg = self.client.messages.create(
                body=message,
                from_=from_number,
                to=to_number
            )
            return {
                "status": "sent",
                "message_sid": msg.sid,
                "from": from_number,
                "to": to_number
            }
        except Exception as e:
            logger.error(f"[TWILIO] SMS failed: {e}")
            return {"status": "failed", "error": str(e)}

    def log_event(self, event_type: str, target_id: str, payload: Dict[str, Any]):
        """Logs to cil_events."""
        event_row = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "actor_type": "SYSTEM",
            "actor_id": "twilio_spoke",
            "actor_role": "SYSTEM",
            "target_type": "PHONE",
            "target_id": target_id,
            "payload": json.dumps(payload),
            "idempotency_key": f"twilio_{uuid.uuid4()}"
        }
        self.bq.client.insert_rows_json("autohaus-infrastructure.autohaus_cil.cil_events", [event_row])

from datetime import datetime
