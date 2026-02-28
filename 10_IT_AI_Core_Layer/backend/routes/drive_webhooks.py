import logging
from fastapi import APIRouter, Request

logger = logging.getLogger("autohaus.drive_webhooks")

drive_webhook_router = APIRouter(tags=["Drive Webhooks"])


@drive_webhook_router.post("/api/webhooks/drive/push")
async def drive_push_notification(request: Request):
    body = await request.json()
    logger.info(f"[DRIVE WEBHOOK] Received push notification: {body}")
    return {"status": "received"}
