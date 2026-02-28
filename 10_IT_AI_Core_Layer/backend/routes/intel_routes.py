import logging
from fastapi import APIRouter, BackgroundTasks
from services.gmail_intel import GmailIntelService
from services.attachment_processor import AttachmentProcessor

logger = logging.getLogger("autohaus.intel_routes")
intel_router = APIRouter(prefix="/api/intel", tags=["intel"])
gmail_service = GmailIntelService()
attachment_processor = AttachmentProcessor()

@intel_router.post("/gmail/scan")
async def trigger_gmail_scan(background_tasks: BackgroundTasks, account: str = None, limit: int = 100):
    """
    Triggers a Gmail scan. If account is provided, scans that account.
    Otherwise, scans all accounts in sequence.
    """
    if account:
        logger.info(f"[INTEL] Triggering scan for {account}")
        background_tasks.add_task(gmail_service.scan_account_full, account, limit)
    else:
        logger.info("[INTEL] Triggering full scan sequence")
        background_tasks.add_task(gmail_service.run_full_scan_sequence, limit)
    
    return {"status": "accepted", "message": "Gmail scan initiated in background"}

@intel_router.post("/attachments/process")
async def trigger_attachment_scan(background_tasks: BackgroundTasks, limit: int = 20):
    logger.info(f"[INTEL] Triggering Tier 0 attachment extraction (limit {limit})")
    background_tasks.add_task(attachment_processor.process_ahsin_attachments, limit)
    return {"status": "accepted", "message": "Attachment processing initiated in background"}

@intel_router.get("/status")
async def get_intel_status():
    return {
        "gmail_intelligence": "active",
        "drive_ambient_ear": "active"
    }
