from fastapi import APIRouter, HTTPException, Depends, Query
from google.cloud import bigquery
from database.policy_engine import get_policy
from database.bigquery_client import BigQueryClient
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging
import google.auth
import uuid
from models.events import CILEvent, EventType, ActorType, TargetType

logger = logging.getLogger("autohaus.compliance")

compliance_router = APIRouter(tags=["compliance"])

PROJECT_ID = "autohaus-infrastructure"
DATASET_ID = "autohaus_cil"

# --- Request Models ---
class TitleReceivedRequest(BaseModel):
    vin: str
    entity: str

class CitResolvedRequest(BaseModel):
    deal_id: str

# --- Security Dependency (ADC Pattern from existing routes) ---
def get_bq_client():
    try:
        credentials, project = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform', 'https://www.googleapis.com/auth/bigquery']
        )
        if hasattr(credentials, 'with_subject'):
            credentials = credentials.with_subject('moaz@autohausia.com')
        return bigquery.Client(credentials=credentials, project=PROJECT_ID)
    except Exception as e:
        logger.error(f"ADC Impersonation Failed: {str(e)}")
        return None

# --- Table Provisioning Flags ---
# NOTE: This flag is initialized on first call and remains sticky until service restart.
# This limitation is acceptable as Cloud Run revisions pick up new infrastructure.
_DEALS_TABLE_PROVISIONED: Optional[bool] = None

def is_deals_provisioned(client: bigquery.Client) -> bool:
    global _DEALS_TABLE_PROVISIONED
    if _DEALS_TABLE_PROVISIONED is not None:
        return _DEALS_TABLE_PROVISIONED
    
    query = f"SELECT table_name FROM `{PROJECT_ID}.{DATASET_ID}.INFORMATION_SCHEMA.TABLES` WHERE table_name = 'deals'"
    try:
        results = list(client.query(query).result())
        _DEALS_TABLE_PROVISIONED = len(results) > 0
    except Exception as e:
        logger.warning(f"Failed to check deals table: {e}")
        _DEALS_TABLE_PROVISIONED = False
    
    return _DEALS_TABLE_PROVISIONED

# ───────────────────────────────────────────────────────────────────────────────
# GET Endpoints
# ───────────────────────────────────────────────────────────────────────────────

@compliance_router.get("/inventory_gauge")
async def inventory_gauge(client: bigquery.Client = Depends(get_bq_client)):
    """Query inventory_master, count units by entity, compare against policies."""
    if not client:
        raise HTTPException(status_code=500, detail="BigQuery unavailable")

    # 1. Fetch thresholds at request time (60s TTL)
    max_units = get_policy("GOVERNANCE", "inventory_max_units", ttl_seconds=60) or 15
    warning_units = get_policy("GOVERNANCE", "inventory_warning_units", ttl_seconds=60) or 13

    # 2. Query
    query = f"SELECT COALESCE(entity, 'UNKNOWN') as entity, COUNT(*) as counts FROM `{PROJECT_ID}.{DATASET_ID}.inventory_master` GROUP BY entity"
    results = client.query(query).result()
    
    data = []
    total_status = "OK"
    for row in results:
        counts = row.counts
        status = "OK"
        if counts >= max_units:
            status = "CRITICAL"
            total_status = "CRITICAL"
        elif counts >= warning_units:
            status = "WARNING"
            if total_status != "CRITICAL":
                total_status = "WARNING"
        
        data.append({
            "entity": row.entity,
            "units": counts,
            "max": max_units,
            "warning": warning_units,
            "status": status
        })

    return {"status": total_status, "entities": data}

@compliance_router.get("/exposure_meter")
async def exposure_meter(client: bigquery.Client = Depends(get_bq_client)):
    """Sum vehicle values from inventory_master, compare against insurance ceiling."""
    if not client:
        raise HTTPException(status_code=500, detail="BigQuery unavailable")

    # 1. Fetch thresholds (60s TTL)
    ceiling = get_policy("FINANCE", "insurance_exposure_ceiling", ttl_seconds=60) or 200000
    warning = get_policy("FINANCE", "insurance_exposure_warning_threshold", ttl_seconds=60) or 180000

    # 2. Query
    query = f"SELECT SUM(purchase_price) as total_exposure FROM `{PROJECT_ID}.{DATASET_ID}.inventory_master`"
    results = list(client.query(query).result())
    total_exposure = results[0].total_exposure if results and results[0].total_exposure else 0

    status = "OK"
    if total_exposure >= ceiling:
        status = "CRITICAL"
    elif total_exposure >= warning:
        status = "WARNING"

    return {
        "status": status,
        "total_exposure": float(total_exposure),
        "ceiling": ceiling,
        "warning_threshold": warning
    }

@compliance_router.get("/title_bottleneck")
async def title_bottleneck(client: bigquery.Client = Depends(get_bq_client)):
    """Query inventory_master for title_status and date_in_stock, compute urgency."""
    if not client:
        raise HTTPException(status_code=500, detail="BigQuery unavailable")

    # 1. Fetch thresholds (60s TTL)
    deadline_days = get_policy("LEGAL", "iowa_title_deadline_days", ttl_seconds=60) or 30

    # 2. Query
    query = f"""
        SELECT id as vin, year as model_year, make, model, date_in_stock, title_status
        FROM `{PROJECT_ID}.{DATASET_ID}.inventory_master`
        WHERE title_status != 'RECEIVED' OR title_status IS NULL
    """
    results = client.query(query).result()
    
    units = []
    for row in results:
        days_in_stock = (datetime.utcnow().date() - row.date_in_stock).days if row.date_in_stock else 0
        days_until_deadline = deadline_days - days_in_stock
        
        urgency = "NORMAL"
        if days_until_deadline <= 0:
            urgency = "IMMEDIATE"
        elif days_until_deadline <= 7:
            urgency = "HIGH"
        elif days_until_deadline <= 14:
            urgency = "ELEVATED"
            
        units.append({
            "vin": row.vin,
            "vehicle": f"{row.model_year} {row.make} {row.model}",
            "days_in_stock": days_in_stock,
            "days_until_deadline": days_until_deadline,
            "status": row.title_status,
            "urgency": urgency
        })

    return {"deadline_days": deadline_days, "bottlenecks": units}

@compliance_router.get("/cit_flags")
async def cit_flags(client: bigquery.Client = Depends(get_bq_client)):
    """Query deals table where deal_state = FUNDED, compute days_since_funding."""
    if not client:
        raise HTTPException(status_code=500, detail="BigQuery unavailable")

    # 1. Provisioning check (table exists check done once at module level)
    if not is_deals_provisioned(client):
        return {"status": "UNAVAILABLE", "reason": "deals table not yet provisioned"}

    # 2. Fetch thresholds (60s TTL)
    aging_threshold = get_policy("GOVERNANCE", "cit_aging_threshold_days", ttl_seconds=60) or 5
    warning_threshold = get_policy("GOVERNANCE", "cit_warning_threshold_days", ttl_seconds=60) or 3

    # 3. Query
    query = f"""
        SELECT deal_id, vin, funding_date 
        FROM `{PROJECT_ID}.{DATASET_ID}.deals` 
        WHERE deal_state = 'FUNDED'
    """
    results = client.query(query).result()
    
    flags = []
    for row in results:
        days_since_funding = (datetime.utcnow().date() - row.funding_date).days if row.funding_date else 0
        
        status = "OK"
        if days_since_funding >= aging_threshold:
            status = "CRITICAL"
        elif days_since_funding >= warning_threshold:
            status = "WARNING"
            
        if status != "OK":
            flags.append({
                "deal_id": row.deal_id,
                "vin": row.vin,
                "days_since_funding": days_since_funding,
                "status": status
            })

    return {"total_flagged": len(flags), "flags": flags}

@compliance_router.get("/stale_inventory")
async def stale_inventory(client: bigquery.Client = Depends(get_bq_client)):
    """Query inventory_master for days_in_stock > threshold."""
    if not client:
        raise HTTPException(status_code=500, detail="BigQuery unavailable")

    # 1. Fetch thresholds (60s TTL)
    threshold = get_policy("GOVERNANCE", "stale_inventory_threshold_days", ttl_seconds=60) or 45

    # 2. Query
    query = f"""
        SELECT id as vin, year as model_year, make, model, date_in_stock, 
               DATE_DIFF(CURRENT_DATE(), date_in_stock, DAY) as days_in_stock
        FROM `{PROJECT_ID}.{DATASET_ID}.inventory_master`
        WHERE DATE_DIFF(CURRENT_DATE(), date_in_stock, DAY) > {threshold}
        ORDER BY days_in_stock DESC
    """
    results = client.query(query).result()
    
    data = []
    for row in results:
        data.append({
            "vin": row.vin,
            "vehicle": f"{row.model_year} {row.make} {row.model}",
            "days_in_stock": row.days_in_stock,
            "date_in_stock": row.date_in_stock.isoformat()
        })

    return {"threshold": threshold, "units": data}


# ───────────────────────────────────────────────────────────────────────────────
# POST Endpoints (Events-Before-State)
# ───────────────────────────────────────────────────────────────────────────────

@compliance_router.post("/title_received")
async def title_received(req: TitleReceivedRequest, client: bigquery.Client = Depends(get_bq_client)):
    """Updates title_status in inventory_master with audit event before."""
    if not client:
        raise HTTPException(status_code=500, detail="BigQuery unavailable")

    bq_wrapper = BigQueryClient() # For insertion logic

    # 1. Write the event BEFORE the state change
    event_id = str(uuid.uuid4())
    event = CILEvent(
        event_id=event_id,
        event_type=EventType.TITLE_STATUS_UPDATED,
        actor_type=ActorType.HUMAN,
        actor_id="MOAZ_SIAL",
        target_type=TargetType.VEHICLE,
        target_id=req.vin,
        payload={
            "old_status": "UNKNOWN", # Ideally fetch first, but brief focus is lineage
            "new_status": "RECEIVED",
            "entity": req.entity
        }
    )

    if not bq_wrapper.insert_cil_event(event):
        raise HTTPException(status_code=500, detail="Failed to log audit event. Action aborted.")

    # 2. Attempt State Change
    query = f"""
        UPDATE `{PROJECT_ID}.{DATASET_ID}.inventory_master`
        SET title_status = 'RECEIVED'
        WHERE id = @vin
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("vin", "STRING", req.vin)]
    )

    try:
        client.query(query, job_config=job_config).result()
    except Exception as e:
        logger.error(f"State change failed for VIN {req.vin}: {e}")
        # 3. Compensating Event
        comp_event = CILEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.STATE_CHANGE_FAILED,
            actor_type=ActorType.SYSTEM,
            target_type=TargetType.VEHICLE,
            target_id=req.vin,
            payload={
                "failed_event_id": event_id,
                "operation": "UPDATE title_status",
                "error": str(e)
            }
        )
        bq_wrapper.insert_cil_event(comp_event)
        raise HTTPException(status_code=500, detail=f"State update failed: {e}")

    return {"status": "SUCCESS", "event_id": event_id}

@compliance_router.post("/cit_resolved")
async def cit_resolved(req: CitResolvedRequest, client: bigquery.Client = Depends(get_bq_client)):
    """Updates deal state with audit event before."""
    if not client:
        raise HTTPException(status_code=500, detail="BigQuery unavailable")

    # 1. Provisioning check
    if not is_deals_provisioned(client):
        return {"status": "UNAVAILABLE", "reason": "deals table not yet provisioned"}

    bq_wrapper = BigQueryClient()

    # 2. Write event BEFORE
    event_id = str(uuid.uuid4())
    event = CILEvent(
        event_id=event_id,
        event_type=EventType.DEAL_STATE_CHANGED,
        actor_type=ActorType.HUMAN,
        actor_id="MOAZ_SIAL",
        target_type=TargetType.TRANSACTION,
        target_id=req.deal_id,
        payload={
            "old_state": "FUNDED",
            "new_state": "RESOLVED"
        }
    )

    if not bq_wrapper.insert_cil_event(event):
        raise HTTPException(status_code=500, detail="Failed to log audit event. Action aborted.")

    # 3. Attempt State Change
    query = f"""
        UPDATE `{PROJECT_ID}.{DATASET_ID}.deals`
        SET deal_state = 'RESOLVED'
        WHERE deal_id = @deal_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("deal_id", "STRING", req.deal_id)]
    )

    try:
        client.query(query, job_config=job_config).result()
    except Exception as e:
        logger.error(f"State change failed for Deal {req.deal_id}: {e}")
        # 4. Compensating Event
        comp_event = CILEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.STATE_CHANGE_FAILED,
            actor_type=ActorType.SYSTEM,
            target_type=TargetType.TRANSACTION,
            target_id=req.deal_id,
            payload={
                "failed_event_id": event_id,
                "operation": "UPDATE deal_state",
                "error": str(e)
            }
        )
        bq_wrapper.insert_cil_event(comp_event)
        raise HTTPException(status_code=500, detail=f"State update failed: {e}")

    return {"status": "SUCCESS", "event_id": event_id}
