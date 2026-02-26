"""
AutoHaus CIL — HITL API Routes
Exposes the HITL state machine via REST endpoints.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

logger = logging.getLogger("autohaus.hitl_routes")

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


@hitl_router.post("/hitl/propose")
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


@hitl_router.post("/hitl/validate")
async def validate_hitl(request: HitlActionRequest):
    """Validate a pending HITL proposal."""
    try:
        from database.bigquery_client import BigQueryClient
        from pipeline.hitl_service import validate
        
        bq = BigQueryClient()
        result = validate(bq.client, request.hitl_event_id)
        
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


@hitl_router.post("/hitl/apply")
async def apply_hitl(request: HitlActionRequest):
    """Apply a validated HITL change (for high-risk actions requiring confirmation)."""
    try:
        from database.bigquery_client import BigQueryClient
        from pipeline.hitl_service import apply
        
        bq = BigQueryClient()
        result = apply(bq.client, request.hitl_event_id)
        
        if result.get("status") == "ERROR":
            raise HTTPException(status_code=400, detail=result.get("reason"))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HITL apply failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
