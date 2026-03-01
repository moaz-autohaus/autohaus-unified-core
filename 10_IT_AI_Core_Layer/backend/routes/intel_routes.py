import logging
import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, HTTPException
from services.gmail_intel import GmailIntelService
from services.attachment_processor import AttachmentProcessor
from database.policy_engine import get_policy
from database.bigquery_client import BigQueryClient
from pipeline.hydration_engine import HydrationEngine, ContextPackage

logger = logging.getLogger("autohaus.intel_routes")
intel_router = APIRouter(prefix="/api/intel", tags=["intel"])
gmail_service = GmailIntelService()
attachment_processor = AttachmentProcessor()
hydration_engine = HydrationEngine()
bq_client = BigQueryClient()

@intel_router.post("/gmail/scan")
async def trigger_gmail_scan(background_tasks: BackgroundTasks, account: str = None, limit: int = 100):
    """
    Triggers a Gmail scan. If account is provided, scans that account.
    Otherwise, scans all accounts in sequence.
    """
    # Step 1: Normalize & Validate Account
    normalized_account_name = None
    if account:
        normalized_account_name = account.strip().lower()
        authorized_accounts = get_policy("CRM", "gmail_authorized_accounts")
        if authorized_accounts:
            if isinstance(authorized_accounts, str):
                auth_list = [a.strip().lower() for a in authorized_accounts.split(',')]
            else:
                auth_list = [str(a).lower() for a in authorized_accounts]
            if normalized_account_name not in auth_list:
                raise HTTPException(status_code=400, detail={
                    "error": "UNAUTHORIZED_ACCOUNT",
                    "message": "Account not in authorized gmail scan list",
                    "authorized_accounts": auth_list
                })

    # Step 2: Validate Limit
    policy_max = get_policy("CRM", "gmail_scan_max_batch")
    if policy_max is None:
        logger.warning("[INTEL] gmail_scan_max_batch policy key not configured, defaulting to 100")
        validated_limit = 100
    else:
        try:
            validated_limit = int(policy_max)
        except ValueError:
            validated_limit = 100

    if limit > validated_limit:
        raise HTTPException(status_code=400, detail={
            "error": "BATCH_LIMIT_EXCEEDED",
            "policy_maximum": validated_limit,
            "requested": limit
        })
    else:
        validated_limit = limit

    # Step 3: Hydrate
    context_package = None
    hydrated = False
    try:
        context_package = await hydration_engine.build_context_package({
            "account": normalized_account_name,
            "input_domain": "CRM"
        })
        hydrated = True
    except Exception as e:
        logger.warning(f"[INTEL] Hydration failed: {e}")
        context_package = ContextPackage(input_reference=normalized_account_name or "ALL_ACCOUNTS")
        hydrated = False

    # Step 4: Log
    job_id = str(uuid.uuid4())
    event_timestamp = datetime.now(timezone.utc).isoformat()
    event_row = {
        "event_id": job_id,
        "event_type": "GMAIL_SCAN_INITIATED",
        "timestamp": event_timestamp,
        "actor_type": "SYSTEM",
        "actor_id": "system",
        "actor_role": "SYSTEM",
        "target_type": "GMAIL_ACCOUNT",
        "target_id": normalized_account_name or "ALL",
        "payload": json.dumps({
            "account": normalized_account_name,
            "batch_limit": validated_limit,
            "context_package_hydrated": hydrated,
            "initiated_at": event_timestamp
        }),
        "metadata": None,
        "idempotency_key": f"gmail_scan_{job_id}"
    }

    if bq_client.client:
        errs = bq_client.client.insert_rows_json(f"{bq_client.project_id}.{bq_client.dataset_id}.cil_events", [event_row])
        if errs:
            logger.error(f"[INTEL] Failed to insert event: {errs}")

    if normalized_account_name:
        logger.info(f"[INTEL] Triggering scan for {normalized_account_name}")
        async def run_scan_with_context(acc: str, lim: int, ctx: ContextPackage):
            await gmail_service.scan_account_full(acc, lim)
        background_tasks.add_task(run_scan_with_context, normalized_account_name, validated_limit, context_package)
    else:
        logger.info("[INTEL] Triggering full scan sequence")
        background_tasks.add_task(gmail_service.run_full_scan_sequence, validated_limit)
    
    return {
        "status": "ACCEPTED",
        "job_id": job_id,
        "account": normalized_account_name,
        "batch_limit": validated_limit,
        "context_hydrated": hydrated
    }

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
