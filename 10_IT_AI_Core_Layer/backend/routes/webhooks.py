from fastapi import APIRouter, Request, HTTPException
import logging
import base64
import json

from integrations.gmail_spoke import GmailMonitor
from database.bigquery_client import BigQueryClient

logger = logging.getLogger("autohaus.webhooks")
webhook_router = APIRouter()

@webhook_router.post("/google-workspace")
async def google_workspace_webhook(request: Request):
    """
    Endpoint for Google Cloud Pub/Sub push notifications.
    These are triggered by Gmail 'watch' or Drive change notifications.
    """
    body = await request.json()
    
    # 1. Pub/Sub envelope extraction
    message = body.get("message", {})
    data_b64 = message.get("data")
    
    if not data_b64:
        return {"status": "ignored", "reason": "no data"}
    
    try:
        data_raw = base64.b64decode(data_b64).decode("utf-8")
        payload = json.loads(data_raw)
        
        logger.info(f"[WEBHOOK] Received push notification: {payload}")
        
        # 2. Route to Gmail Monitor
        # Note: Payload for Gmail watch includes: {"emailAddress": "...", "historyId": ...}
        if "emailAddress" in payload:
            monitor = GmailMonitor()
            res = await monitor.process_incoming_webhook(payload)
            return res
            
        return {"status": "unrecognized_payload"}
        
    except Exception as e:
        logger.error(f"[WEBHOOK] Processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
