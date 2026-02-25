"""
AutoHaus C-OS v3.1 — MODULE 7: Client JIT Portal (Quote Routes)
================================================================
Backend API endpoints for the public-facing Digital Quote approval system.

Endpoints:
  GET  /api/public/quote/{uuid}  → Fetch a quote's Digital Twin payload
  POST /api/public/quote/approve → Submit customer approval for line items

KAMM Compliance:
  If quote_type is 'VEHICLE_SALE', the response includes a KAMM-branded
  Iowa Damage Disclosure flag that the frontend must render.

MSO Purity:
  Approvals are logged to the system_audit_ledger but do NOT trigger
  financial transactions directly. The CIL processes billing separately.

Author: AutoHaus CIL Build System
Version: 1.0.0
"""

import json
import logging
import os
import uuid as uuid_lib
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from google.cloud import bigquery
import google.auth
from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/auth/.env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("autohaus.quote_portal")

PROJECT_ID = "autohaus-infrastructure"
DATASET_ID = "autohaus_cil"
LEDGER_TABLE = f"{PROJECT_ID}.{DATASET_ID}.system_audit_ledger"

quote_router = APIRouter()


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
# Mock Quote Data (replaced with BigQuery queries in production)
# ---------------------------------------------------------------------------
MOCK_QUOTES = {
    "demo-quote-001": {
        "quote_id": "demo-quote-001",
        "quote_type": "SERVICE_REPAIR",
        "customer_name": "John Smith",
        "vehicle": "2022 BMW M4 Competition",
        "vin": "WBS43AZ0XNC123456",
        "entity": "AUTOHAUS_SERVICES_LLC",
        "entity_brand": "AutoHaus Service Lane",
        "created_at": "2026-02-24T10:00:00Z",
        "expires_at": "2026-02-27T10:00:00Z",
        "tech_video_url": "",
        "line_items": [
            {
                "id": "li-001",
                "description": "Front Brake Pad Replacement",
                "severity": "CRITICAL",
                "cost": 485.00,
                "labor_hours": 1.5,
                "notes": "Pads at 2mm. Metal-on-metal contact detected.",
            },
            {
                "id": "li-002",
                "description": "Subframe Rust Treatment",
                "severity": "CRITICAL",
                "cost": 950.00,
                "labor_hours": 3.0,
                "notes": "Significant corrosion on rear subframe mounting points.",
            },
            {
                "id": "li-003",
                "description": "Coolant Flush & Fill",
                "severity": "MONITOR",
                "cost": 189.00,
                "labor_hours": 0.5,
                "notes": "Coolant at 60% concentration. Recommend flush.",
            },
            {
                "id": "li-004",
                "description": "Tire Rotation & Balance",
                "severity": "GOOD",
                "cost": 89.00,
                "labor_hours": 0.5,
                "notes": "Even wear pattern. Routine maintenance.",
            },
        ],
        "total_estimate": 1713.00,
        "kamm_disclosure_required": False,
    },
    "demo-quote-002": {
        "quote_id": "demo-quote-002",
        "quote_type": "VEHICLE_SALE",
        "customer_name": "Sarah Chen",
        "vehicle": "2024 Porsche 911 Carrera T",
        "vin": "WP0AB2A93RS227890",
        "entity": "KAMM_LLC",
        "entity_brand": "KAMM Compliance",
        "created_at": "2026-02-24T14:00:00Z",
        "expires_at": "2026-03-01T14:00:00Z",
        "tech_video_url": "",
        "line_items": [
            {
                "id": "li-010",
                "description": "Vehicle Purchase — 2024 Porsche 911 Carrera T",
                "severity": "GOOD",
                "cost": 128500.00,
                "labor_hours": 0,
                "notes": "Certified Pre-Owned. 4,200 miles.",
            },
            {
                "id": "li-011",
                "description": "Iowa Title Transfer & Registration",
                "severity": "GOOD",
                "cost": 450.00,
                "labor_hours": 0,
                "notes": "Processed by KAMM LLC — Dealer Compliance HQ.",
            },
        ],
        "total_estimate": 128950.00,
        "kamm_disclosure_required": True,
    },
}


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------
class ApprovalRequest(BaseModel):
    quote_id: str
    approved_items: list[str]  # List of line item IDs
    customer_signature: str = ""
    sms_verification_code: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@quote_router.get("/public/quote/{quote_uuid}")
async def get_quote(quote_uuid: str):
    """
    Fetch a Digital Twin quote payload for the customer-facing portal.
    """
    quote = MOCK_QUOTES.get(quote_uuid)

    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found or expired.")

    logger.info(f"[QUOTE] Serving quote {quote_uuid} for {quote['customer_name']}")
    return quote


@quote_router.post("/public/quote/approve")
async def approve_quote(request: ApprovalRequest):
    """
    Process a customer's approval of selected quote line items.

    If any approved item exceeds $1,000, an SMS verification step
    is required (placeholder for Twilio subaccount integration).
    """
    quote = MOCK_QUOTES.get(request.quote_id)

    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found.")

    # Calculate approved total
    approved_items = [
        item for item in quote["line_items"]
        if item["id"] in request.approved_items
    ]
    approved_total = sum(item["cost"] for item in approved_items)

    # SMS verification gate for high-value approvals
    high_value_items = [i for i in approved_items if i["cost"] > 1000]
    if high_value_items and not request.sms_verification_code:
        return {
            "status": "sms_verification_required",
            "message": f"Items totaling ${approved_total:,.2f} require SMS verification.",
            "high_value_items": [i["description"] for i in high_value_items],
            "action": "A verification code has been sent to your phone.",
        }

    # Log approval to audit ledger
    logger.info(
        f"[QUOTE APPROVED] {request.quote_id} | "
        f"Items: {len(approved_items)} | Total: ${approved_total:,.2f}"
    )

    # Write to BigQuery audit ledger (production)
    client = _get_bq_client()
    if client:
        try:
            audit_record = {
                "event_id": str(uuid_lib.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "QUOTE_APPROVED_BY_CUSTOMER",
                "entity_id": quote.get("vin", ""),
                "entity_type": "VEHICLE",
                "performed_by": quote.get("customer_name", "Customer"),
                "metadata": json.dumps({
                    "quote_id": request.quote_id,
                    "approved_items": request.approved_items,
                    "approved_total": approved_total,
                    "entity": quote.get("entity", ""),
                }),
            }
            errors = client.insert_rows_json(LEDGER_TABLE, [audit_record])
            if errors:
                logger.error(f"Audit ledger insert failed: {errors}")
        except Exception as e:
            logger.error(f"Audit logging failed: {e}")

    return {
        "status": "approved",
        "quote_id": request.quote_id,
        "approved_items": len(approved_items),
        "approved_total": approved_total,
        "message": f"Thank you! Your approval for ${approved_total:,.2f} has been recorded.",
        "entity": quote.get("entity_brand", "AutoHaus"),
    }
