
import os
import uuid
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel
from datetime import datetime

from database.bigquery_client import BigQueryClient
from pipeline.hitl_service import propose, ActionType

logger = logging.getLogger("autohaus.media_routes")
media_router = APIRouter(tags=["Media"])

class MediaIngestResponse(BaseModel):
    proposal_id: str
    status: str
    requires_approval: bool
    proposed_actions: List[dict]

@media_router.post("/ingest", response_model=MediaIngestResponse)
async def ingest_media(
    file: UploadFile = File(...),
    actor_id: str = Form(...),
    actor_role: str = Form("STANDARD"),
    doc_type_hint: Optional[str] = Form(None)
):
    """
    Sandbox-First Media Ingestion.
    1. Uploads file to temporary storage.
    2. Performs analysis (Vision/Extraction).
    3. Creates a HITL Proposal.
    """
    try:
        # Step 1: Save file temporarily (Simulated for now, would go to Drive/Storage)
        file_id = str(uuid.uuid4())
        content = await file.read()
        
        # Step 2: Simulated Gemini Analysis
        # In production, this would call extraction_engine.py
        mock_extraction = {
            "vin": "WBA93HM0XP1234567",
            "doc_type": doc_type_hint or "AUCTION_RECEIPT",
            "extracted_facts": {
                "mileage": "14,200",
                "condition": "Damaged",
                "auction_date": "2026-02-21"
            }
        }
        
        # Step 3: Create HITL Proposal
        bq = BigQueryClient()
        proposal_payload = {
            "file_id": file_id,
            "filename": file.filename,
            "extraction": mock_extraction,
            "actions": [
                {"type": "CREATE_DOCUMENT", "params": {"doc_type": mock_extraction["doc_type"]}},
                {"type": "UPDATE_FACTS", "params": mock_extraction["extracted_facts"]}
            ]
        }
        
        result = propose(
            bq_client=bq.client,
            actor_user_id=actor_id,
            actor_role=actor_role,
            action_type="MEDIA_INGEST", # We will add this to ActionType
            target_type="DOCUMENT",
            target_id=file_id,
            payload=proposal_payload,
            reason=f"New document upload: {file.filename}",
            source="UI_UPLOAD"
        )
        
        if result.get("status") == "REJECTED":
            raise HTTPException(status_code=403, detail=result.get("reason"))
            
        return MediaIngestResponse(
            proposal_id=result["hitl_event_id"],
            status="PROPOSED",
            requires_approval=True,
            proposed_actions=proposal_payload["actions"]
        )
        
    except Exception as e:
        logger.error(f"Media ingest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@media_router.get("/proposals/pending")
async def get_pending_proposals():
    """Returns a list of pending HITL proposals for the Dashboard."""
    bq = BigQueryClient()
    query = """
        SELECT * FROM `autohaus_cil.hitl_events`
        WHERE status = 'PROPOSED'
        ORDER BY created_at DESC
        LIMIT 20
    """
    try:
        results = list(bq.client.query(query).result())
        return [dict(r) for r in results]
    except Exception as e:
        logger.error(f"Failed to fetch proposals: {e}")
        return []
