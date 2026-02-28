"""
AutoHaus CIL — HITL API Routes
Exposes the HITL state machine via REST endpoints.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any

import logging
import traceback
from fastapi import APIRouter, HTTPException

logger = logging.getLogger("autohaus.hitl_routes")

def serialize_hitl(obj):
    """Recursively convert NON-JSON objects to strings."""
    if isinstance(obj, list):
        return [serialize_hitl(i) for i in obj]
    if isinstance(obj, dict):
        return {str(k): serialize_hitl(v) for k, v in obj.items()}
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    return str(obj)

hitl_router = APIRouter(tags=["HITL"])


class HitlProposeRequest(BaseModel):
    actor_user_id: str
    actor_role: str  # SOVEREIGN | STANDARD | FIELD
    action_type: str  # CONTEXT_ADD | FIELD_OVERRIDE | ENTITY_MERGE | etc.
    target_type: str  # DOCUMENT | ENTITY
    target_id: str
    payload: Dict[str, Any]
    reason: Optional[str] = None
    source: str = "COS_CHAT"


class HitlActionRequest(BaseModel):
    hitl_event_id: str


@hitl_router.post("/propose")
async def propose_hitl(request: HitlProposeRequest):
    """Create a new HITL proposal."""
    try:
        from database.bigquery_client import BigQueryClient
        from pipeline.hitl_service import propose
        
        bq = BigQueryClient()
        result = propose(
            bq_client=bq.client,
            actor_user_id=request.actor_user_id,
            actor_role=request.actor_role,
            action_type=request.action_type,
            target_type=request.target_type,
            target_id=request.target_id,
            payload=request.payload,
            reason=request.reason,
            source=request.source,
        )
        
        if result.get("status") == "REJECTED":
            raise HTTPException(status_code=403, detail=result.get("reason"))
        if result.get("status") == "ERROR":
            raise HTTPException(status_code=500, detail=result.get("reason"))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HITL propose failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@hitl_router.post("/validate")
async def validate_hitl(request: HitlActionRequest):
    """Validate a pending HITL proposal."""
    try:
        from database.bigquery_client import BigQueryClient
        from pipeline.hitl_service import validate
        
        bq = BigQueryClient()
        result = await validate(bq.client, request.hitl_event_id)
        
        if result.get("status") == "REJECTED":
            raise HTTPException(status_code=422, detail=result)
        if result.get("status") == "ERROR":
            raise HTTPException(status_code=400, detail=result.get("reason"))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HITL validate failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@hitl_router.post("/apply")
async def apply_hitl(request: HitlActionRequest):
    """Apply a validated HITL change (for high-risk actions requiring confirmation)."""
    try:
        from database.bigquery_client import BigQueryClient
        from pipeline.hitl_service import apply
        
        bq = BigQueryClient()
        result = await apply(bq.client, request.hitl_event_id)
        
        if result.get("status") == "ERROR":
            raise HTTPException(status_code=400, detail=result.get("reason"))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HITL apply failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@hitl_router.get("/queue")
async def get_hitl_queue():
    """Returns the pending HITL approval queue."""
    try:
        from database.bigquery_client import BigQueryClient
        bq = BigQueryClient()
        logger.info("[HITL] Fetching approval queue...")
        
        query = f"""
            WITH latest_events AS (
                SELECT *,
                ROW_NUMBER() OVER(PARTITION BY hitl_event_id ORDER BY created_at DESC) as rank
                FROM `{bq.project_id}.{bq.dataset_id}.hitl_events`
            )
            SELECT * EXCEPT(rank)
            FROM latest_events
            WHERE rank = 1
            AND status IN ('PROPOSED', 'VALIDATED')
            AND (
                TO_JSON_STRING(payload) NOT LIKE '%"source":"GMAIL_%'
                OR TO_JSON_STRING(payload) LIKE '%"source":"TIER0_% '
                OR TO_JSON_STRING(payload) LIKE '%"evidence_tier"%'
            )
            ORDER BY created_at DESC
        """
        
        results = bq.client.query(query).result()
        queue = []
        for row in results:
            item = dict(row)
            # Replit UI compatibility: provide both 'id' and 'hitl_event_id'
            item["id"] = item["hitl_event_id"]
            queue.append(item)
            
        logger.info(f"[HITL] Queue fetched: {len(queue)} items.")
        return serialize_hitl(queue)
    except Exception as e:
        logger.error(f"Failed to fetch HITL queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@hitl_router.post("/{event_id}/approve")
async def approve_hitl_event(event_id: str):
    """Convenience endpoint for the UI to approve and execute a proposal."""
    logger.info(f"[HITL] UI Request: Approve {event_id}")
    try:
        from database.bigquery_client import BigQueryClient
        from pipeline.hitl_service import validate, apply
        
        bq = BigQueryClient()
        
        # 0. Fetch current status
        from pipeline.hitl_service import _fetch_hitl_event
        current = _fetch_hitl_event(bq.client, event_id)
        if not current:
             raise HTTPException(status_code=404, detail="Event not found")
             
        status = current.get("status")
        
        # 1. Validate if needed
        if status == "PROPOSED":
            v_res = await validate(bq.client, event_id)
            logger.info(f"[HITL] Validation result for {event_id}: {v_res}")
            if v_res.get("status") == "REJECTED":
                return serialize_hitl(v_res)
            if v_res.get("auto_applied"):
                return serialize_hitl({"status": "APPLIED", "hitl_event_id": event_id, "detail": "Auto-applied during validation"})
            status = v_res.get("status")
        
        # 2. Apply if Validated
        if status == "VALIDATED":
            a_res = await apply(bq.client, event_id)
            logger.info(f"[HITL] Manual apply result for {event_id}: {a_res.get('status')}")
            return serialize_hitl(a_res)
            
        if status == "APPLIED":
             return serialize_hitl({"status": "APPLIED", "hitl_event_id": event_id, "detail": "Already applied"})

        raise HTTPException(status_code=400, detail=f"Cannot approve from state: {status}")
            
        return serialize_hitl(v_res)
    except Exception as e:
        logger.error(f"Approve failed for {event_id}: {e}")
        error_trace = traceback.format_exc()
        logger.error(error_trace)
        raise HTTPException(status_code=500, detail=error_trace)


@hitl_router.post("/{event_id}/reject")
async def reject_hitl_event(event_id: str, reason: Optional[str] = "Rejected by user"):
    """Manually reject a proposal."""
    try:
        from database.bigquery_client import BigQueryClient
        from pipeline.hitl_service import _update_hitl_status
        from datetime import datetime
        
        bq = BigQueryClient()
        await _update_hitl_status(bq.client, event_id, "REJECTED", {
            "reason": reason,
            "validated_at": datetime.utcnow().isoformat()
        })
        return {"status": "REJECTED", "hitl_event_id": event_id}
    except Exception as e:
        logger.error(f"Reject failed for {event_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
