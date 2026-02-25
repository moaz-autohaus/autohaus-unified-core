"""
AutoHaus C-OS v3.1 — MODULE 8: Logistics Tracking (P&D Driver Maps)
====================================================================
Backend API for receiving Google AppSheet driver GPS updates and
dispatching live tracking links to customers via Twilio SMS.

Endpoints:
  POST /api/logistics/location → Receives AppSheet webhook payload.

Workflow:
  1. Driver hits "Start Route" in AppSheet, which POSTs coordinates
     and the customer's phone number to this endpoint.
  2. The CIL logs the location to BigQuery (`system_audit_ledger`).
  3. If status == 'EN_ROUTE', it triggers a Twilio SMS to the customer
     containing a unique link to the React Tracking Portal.

Entity Rule:
  Logistics operations are performed by FLUIDITRUCK_LLC or CARLUX_LLC.

Author: AutoHaus CIL Build System
Version: 1.0.0
"""

import json
import logging
import os
import uuid as uuid_lib
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from google.cloud import bigquery
import google.auth
from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/auth/.env"))

# ---------------------------------------------------------------------------
# Configuration & Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("autohaus.logistics")

PROJECT_ID = "autohaus-infrastructure"
DATASET_ID = "autohaus_cil"
LEDGER_TABLE = f"{PROJECT_ID}.{DATASET_ID}.system_audit_ledger"

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")
UI_BASE_URL = os.environ.get("UI_BASE_URL", "https://autohaus-command.replit.app")

logistics_router = APIRouter()


# ---------------------------------------------------------------------------
# BigQuery Client
# ---------------------------------------------------------------------------
def _get_bq_client() -> Optional[bigquery.Client]:
    try:
        credentials, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        if hasattr(credentials, "with_subject"):
            credentials = credentials.with_subject("moaz@autohausia.com")
        return bigquery.Client(credentials=credentials, project=PROJECT_ID)
    except Exception as e:
        logger.error(f"BigQuery client failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------
class LocationUpdate(BaseModel):
    job_id: str
    driver_id: str
    latitude: float
    longitude: float
    status: str             # "EN_ROUTE", "ARRIVED", "COMPLETED"
    customer_phone: Optional[str] = None
    entity: str = "FLUIDITRUCK_LLC"


# ---------------------------------------------------------------------------
# Background Task: Dispatch SMS
# ---------------------------------------------------------------------------
def dispatch_tracking_sms(phone: str, job_id: str, driver_id: str, entity: str):
    """
    Sends a tracking link via Twilio SMS to the customer.
    Runs asynchronously to unblock the API response to AppSheet.
    """
    tracking_url = f"{UI_BASE_URL}/track/{job_id}"
    
    brand = "Fluiditruck Fleet" if entity == "FLUIDITRUCK_LLC" else "Carlux Logistics"
    
    message_body = (
        f"AutoHaus Update:\n"
        f"Your driver ({driver_id}) is en route.\n\n"
        f"Track your vehicle live here:\n{tracking_url}\n\n"
        f"— {brand}"
    )

    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
        logger.warning(f"[TWILIO DISABLED] Would send SMS to {phone}: {message_body}")
        return

    try:
        from twilio.rest import Client as TwilioClient
        client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=message_body,
            from_=TWILIO_PHONE_NUMBER,
            to=phone
        )
        logger.info(f"[LOGISTICS SMS] Sent tracking link to {phone}. SID: {message.sid}")
    except Exception as e:
        logger.error(f"[LOGISTICS SMS] Failed to send to {phone}: {e}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@logistics_router.post("/location")
async def update_location(payload: LocationUpdate, background_tasks: BackgroundTasks):
    """
    AppSheet Webhook endpoint for Driver GPS tracking.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    
    logger.info(
        f"[LOGISTICS UPDATE] Job {payload.job_id} | Driver {payload.driver_id} | "
        f"Status: {payload.status} | Location: {payload.latitude}, {payload.longitude}"
    )

    # 1. Dispatch SMS if EN_ROUTE (AppSheet trigger)
    if payload.status == "EN_ROUTE" and payload.customer_phone:
        background_tasks.add_task(
            dispatch_tracking_sms,
            payload.customer_phone,
            payload.job_id,
            payload.driver_id,
            payload.entity
        )

    # 2. Write location trace to BigQuery Audit Ledger
    client = _get_bq_client()
    if client:
        try:
            audit_record = {
                "event_id": str(uuid_lib.uuid4()),
                "timestamp": timestamp,
                "action": f"LOGISTICS_{payload.status}",
                "entity_id": payload.job_id,
                "entity_type": "LOGISTICS_JOB",
                "performed_by": payload.driver_id,
                "metadata": json.dumps({
                    "latitude": payload.latitude,
                    "longitude": payload.longitude,
                    "entity": payload.entity,
                    "status": payload.status
                }),
            }
            errors = client.insert_rows_json(LEDGER_TABLE, [audit_record])
            if errors:
                logger.error(f"Audit ledger insert failed: {errors}")
        except Exception as e:
            logger.error(f"Audit logging failed: {e}")

    return {
        "status": "success",
        "job_id": payload.job_id,
        "recorded_at": timestamp
    }
