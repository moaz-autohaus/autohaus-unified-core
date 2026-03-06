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

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel

from google.cloud import bigquery
import google.auth
from dotenv import load_dotenv

from database.policy_engine import get_policy
from pipeline.hydration_engine import HydrationEngine, ContextPackage

load_dotenv(os.path.expanduser("~/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/auth/.env"))

# ---------------------------------------------------------------------------
# Configuration & Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("autohaus.logistics")

hydration_engine = HydrationEngine()

PROJECT_ID = "autohaus-infrastructure"
DATASET_ID = "autohaus_cil"
LEDGER_TABLE = f"{PROJECT_ID}.{DATASET_ID}.system_audit_ledger"

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")
UI_BASE_URL = os.getenv("UI_BASE_URL")

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
    Wrapped in Normalize → Validate → Hydrate → Log pipeline.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Step 1: Normalize
    status = payload.status.upper().strip()
    if not (-90.0 <= payload.latitude <= 90.0 and -180.0 <= payload.longitude <= 180.0):
        raise HTTPException(status_code=400, detail={
            "error": "INVALID_COORDINATES",
            "message": "GPS coordinates out of valid range"
        })

    # Step 2: Validate
    allowed_statuses = get_policy("LOGISTICS", "logistics_valid_statuses")
    if not allowed_statuses:
        allowed_statuses = ["EN_ROUTE", "DELIVERED", "IDLE", "BREAKDOWN"]
    elif isinstance(allowed_statuses, str):
        allowed_statuses = [s.strip().upper() for s in allowed_statuses.split(",")]
    else:
        allowed_statuses = [str(s).upper() for s in allowed_statuses]

    if status not in allowed_statuses:
        raise HTTPException(status_code=400, detail={
            "error": "INVALID_STATUS",
            "allowed_values": allowed_statuses,
            "received": status
        })

    bq = _get_bq_client()
    if bq:
        driver_query = f"""
            SELECT person_id 
            FROM `{PROJECT_ID}.{DATASET_ID}.master_person_graph`
            WHERE person_id = @driver_id
            LIMIT 1
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("driver_id", "STRING", payload.driver_id)]
        )
        try:
            results = list(bq.query(driver_query, job_config=job_config).result())
            if len(results) == 0:
                raise HTTPException(status_code=404, detail={
                    "error": "DRIVER_NOT_FOUND",
                    "driver_id": payload.driver_id
                })
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"[LOGISTICS] Could not validate Driver ID against BQ: {e}")

    # Step 3: Hydrate
    context_package = None
    hydrated = False
    try:
        context_package = await hydration_engine.build_context_package({
            "person_id": payload.driver_id,
            "input_domain": "LOGISTICS"
        })
        hydrated = True
    except Exception as e:
        logger.warning(f"[LOGISTICS] Hydration failed: {e}")
        context_package = ContextPackage(input_reference=payload.driver_id)

    # Step 4: Log (Event Spine first)
    if bq:
        event_row = {
            "event_id": str(uuid_lib.uuid4()),
            "event_type": "LOCATION_UPDATE",
            "timestamp": timestamp,
            "actor_type": "PERSON",
            "actor_id": payload.driver_id,
            "actor_role": "DRIVER",
            "target_type": "LOGISTICS_JOB",
            "target_id": payload.job_id,
            "payload": json.dumps({
                "coordinates": {"lat": payload.latitude, "lng": payload.longitude},
                "status": status,
                "context_package_hydrated": hydrated,
                "recorded_at": timestamp
            }),
            "metadata": None,
            "idempotency_key": f"loc_{payload.job_id}_{timestamp}"
        }
        try:
            errs = bq.insert_rows_json(f"{PROJECT_ID}.{DATASET_ID}.cil_events", [event_row])
            if errs:
                logger.error(f"[LOGISTICS] cil_events insert failed: {errs}")
        except Exception as e:
            logger.error(f"[LOGISTICS] cil_events logging failed: {e}")

    logger.info(
        f"[LOGISTICS UPDATE] Job {payload.job_id} | Driver {payload.driver_id} | "
        f"Status: {status} | Location: {payload.latitude}, {payload.longitude}"
    )

    # Dispatch SMS if EN_ROUTE
    if status == "EN_ROUTE" and payload.customer_phone:
        background_tasks.add_task(
            dispatch_tracking_sms,
            payload.customer_phone,
            payload.job_id,
            payload.driver_id,
            payload.entity
        )

    # Continue to system_audit_ledger
    client = bq
    if client:
        try:
            audit_record = {
                "event_id": str(uuid_lib.uuid4()),
                "timestamp": timestamp,
                "action": f"LOGISTICS_{status}",
                "entity_id": payload.job_id,
                "entity_type": "LOGISTICS_JOB",
                "performed_by": payload.driver_id,
                "metadata": json.dumps({
                    "latitude": payload.latitude,
                    "longitude": payload.longitude,
                    "entity": payload.entity,
                    "status": status,
                    "context_package": context_package.model_dump(mode='json') if context_package else None
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

@logistics_router.get("/active")
async def get_active_logistics(client: bigquery.Client = Depends(_get_bq_client)):
    """
    Returns a list of active logistics shipments for the Dashboard.
    """
    data = {
        "active_shipments": []
    }
    
    if not client:
        return data

    try:
        # Fetch from BigQuery (where status is EN_ROUTE)
        # Note: This query depends on the actual structure of logistics data if stored elsewhere
        # Using audit ledger as a fallback to see recent en_route events
        query = f"""
            SELECT entity_id as id, timestamp as detected_at, metadata
            FROM `{LEDGER_TABLE}`
            WHERE action = 'LOGISTICS_EN_ROUTE'
            ORDER BY timestamp DESC
            LIMIT 10
        """
        query_job = client.query(query)
        results = []
        for row in query_job:
            meta = json.loads(row.metadata) if isinstance(row.metadata, str) else row.metadata
            results.append({
                "id": row.id,
                "vin": meta.get("vin", "UNKNOWN"),
                "origin": "Processing Center",
                "destination": "Facility",
                "status": "IN_TRANSIT",
                "eta": None
            })
        data["active_shipments"] = results
        return data
    except Exception as e:
        print(f"Logistics active fetch error: {e}")
        return data
