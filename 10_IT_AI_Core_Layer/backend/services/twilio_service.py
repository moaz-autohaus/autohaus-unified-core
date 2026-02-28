import os
import json
import logging
import uuid
from typing import Optional, Dict, Any
from twilio.rest import Client
from database.policy_engine import get_policy
from database.bigquery_client import BigQueryClient

logger = logging.getLogger("autohaus.twilio_service")

class TwilioService:
    """
    AutoHaus Twilio Service — A2P 10DLC Anchored
    Manages outbound SMS with verified KAMM LLC branding and trust anchors.
    """
    
    # A2P Trust Anchors (Hardcoded as secondary source of truth)
    A2P_BRAND_SID = "BN5b385ff6d76c9a7c7f7bfb6e7dc6f510"
    A2P_TRUST_BUNDLE_SID = "BU589ff4081a62f5a27db74760369853ec"
    A2P_PROFILE_SID = "BU8cffa57716e9d6d5fac1681b0085ba69"
    A2P_EXTERNAL_BRAND_ID = "BQ7IRE3"

    def __init__(self, bq_client=None):
        self.bq = bq_client or BigQueryClient()
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        self.client = None
        
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            logger.warning("[TWILIO] Missing credentials. Outbound SMS will be SIMULATED.")

    async def send_sms(self, to_number: str, message: str, purpose: str = "CIL_OPS") -> Dict[str, Any]:
        """
        Send an A2P-compliant SMS.
        """
        # 1. Resolve Number from Policy Engine
        from_number = get_policy("TWILIO", f"{purpose}_NUMBER")
        if not from_number:
            from_number = os.environ.get("TWILIO_PHONE_NUMBER")
            
        if not from_number:
            return {"status": "failed", "error": f"No registered number found for {purpose}"}

        # 2. Prepare Meta-context (Advanced headers/SIDs if needed by Twilio in future)
        # Twilio manages A2P routing via the phone number association, 
        # but we track the anchors for audit and compliance.
        anchors = {
            "brand_sid": self.A2P_BRAND_SID,
            "external_brand_id": self.A2P_EXTERNAL_BRAND_ID
        }

        logger.info(f"[TWILIO] Dispatching {purpose} SMS to {to_number} via {from_number} (A2P Verified)")

        if not self.client:
            logger.info(f"[SIMULATED SMS] Branding: KAMM LLC | From: {from_number} | To: {to_number} | Body: {message}")
            return {"status": "simulated", "message_sid": f"SM{uuid.uuid4().hex}"}

        try:
            # We use the verified KAMM LLC sender
            msg = self.client.messages.create(
                body=message,
                from_=from_number,
                to=to_number
            )
            
            # Log successful dispatch with anchors
            self.log_event("TWILIO_SMS_DISPATCHED", to_number, {
                "sid": msg.sid,
                "purpose": purpose,
                "from": from_number,
                "a2p_anchors": anchors
            })
            
            return {
                "status": "sent",
                "message_sid": msg.sid,
                "from": from_number,
                "to": to_number,
                "a2p_verified": True
            }
        except Exception as e:
            logger.error(f"[TWILIO] A2P SMS dispatch failed: {e}")
            return {"status": "failed", "error": str(e)}

    def log_event(self, event_type: str, target_id: str, payload: Dict[str, Any]):
        """Logs to BigQuery Audit Spine."""
        from datetime import datetime
        event_row = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "actor_type": "SYSTEM",
            "actor_id": "twilio_service",
            "actor_role": "SYSTEM",
            "target_type": "PHONE",
            "target_id": target_id,
            "payload": json.dumps(payload),
            "idempotency_key": f"twilio_svc_{uuid.uuid4()}"
        }
        try:
            self.bq.client.insert_rows_json("autohaus-infrastructure.autohaus_cil.cil_events", [event_row])
        except Exception as e:
            logger.error(f"Failed to log twilio event: {e}")
