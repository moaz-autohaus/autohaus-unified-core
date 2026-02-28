
import logging
from fastapi import APIRouter, Request, BackgroundTasks, Header
from services.drive_ear import drive_ear

logger = logging.getLogger("autohaus.drive_webhook")
drive_webhook_router = APIRouter(prefix="/api/webhooks/drive", tags=["webhooks"])

@drive_webhook_router.post("/push")
async def drive_push_handler(
    request: Request,
    background_tasks: BackgroundTasks,
    x_goog_resource_state: str = Header(None),
    x_goog_resource_id: str = Header(None),
    x_goog_channel_id: str = Header(None)
):
    """
    Handles POST notifications from Google Drive API.
    Resource states: 'sync', 'add', 'update', 'trash', 'untrash', 'change'
    """
    logger.info(f"[DRIVE WEBHOOK] Received state: {x_goog_resource_state} for Resource: {x_goog_resource_id}")

    if x_goog_resource_state == "sync":
        logger.info("[DRIVE WEBHOOK] Sync notification received. Channel verified.")
        return {"status": "verified"}

    # Trigger a folder scan in the background to handle the change
    # We use a background task to respond to Google FAST (within 10s)
    background_tasks.add_task(drive_ear.check_for_new_files)

    return {"status": "received"}
