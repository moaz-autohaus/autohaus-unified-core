
import os
import uuid
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel
from datetime import datetime, timezone

from database.bigquery_client import BigQueryClient
from pipeline.hitl_service import propose, ActionType

logger = logging.getLogger("autohaus.media_routes")
media_router = APIRouter(tags=["Media"])

class MediaIngestResponse(BaseModel):
    proposal_id: str
    status: str
    requires_approval: bool
    proposed_actions: List[dict]
    extracted_claims: List[dict]

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
        
        # Step 2: Real Gemini Analysis
        is_pdf = file.filename.lower().endswith(".pdf") or file.content_type == "application/pdf"
        extracted_data = {}
        claims = []
        
        if is_pdf:
            from services.attachment_processor import attachment_processor, unpack_to_claims
            from models.claims import ClaimSource
            extracted_data = await attachment_processor._extract_tier0_metrics(
                content, file.filename, "UI_UPLOAD", "UI_UPLOAD"
            )
            if extracted_data:
                lineage = {
                    "model": "gemini-2.5-flash",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                claims = unpack_to_claims(
                    raw_response=extracted_data,
                    source=ClaimSource.MEDIA,
                    extractor_identity="media_routes.ingest_media",
                    input_reference=file_id,
                    source_lineage=lineage
                )
        else:
            from pipeline.extraction_engine import classify_document, extract_fields
            from models.claims import ClaimSource, ExtractedClaim
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            
            text_content = content.decode("utf-8", errors="ignore")
            loop = asyncio.get_running_loop()
            
            try:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    doc_type, conf = await asyncio.wait_for(
                        loop.run_in_executor(executor, classify_document, text_content),
                        timeout=30.0
                    )
                    extracted_data = await asyncio.wait_for(
                        loop.run_in_executor(executor, extract_fields, text_content, doc_type, file_id),
                        timeout=45.0
                    )
                    if extracted_data is None:
                        extracted_data = {}
            except asyncio.TimeoutError:
                logger.error("Timeout during Gemini text extraction")
                extracted_data = {}
                doc_type = "UNKNOWN"
            except Exception as e:
                logger.error(f"Error during Gemini text extraction: {e}")
                extracted_data = {}
                doc_type = "UNKNOWN"
            
            if extracted_data and "fields" in extracted_data:
                lineage = {
                    "model": "gemini-flash-latest",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "extraction_version_id": extracted_data.get("extraction_version_id")
                }
                for field_name, field_data in extracted_data["fields"].items():
                    val_str = str(field_data["value"]) if field_data["value"] is not None else "null"
                    field_lineage = dict(lineage)
                    if val_str == "VIN_NOT_PROVIDED":
                        field_lineage["stub_type"] = "STUB_PENDING_VIN"

                    claim = ExtractedClaim(
                        source=ClaimSource.MEDIA,
                        extractor_identity="extraction_engine.extract_fields",
                        input_reference=file_id,
                        entity_type="DOCUMENT",
                        target_field=field_name,
                        extracted_value=val_str,
                        confidence=field_data["confidence"],
                        source_lineage=field_lineage
                    )
                    claims.append(claim)

        # Step 3: Create HITL Proposal
        bq = BigQueryClient()

        # Wire conflict_detector.process_claim into media_routes.py before HITL proposal is built
        from pipeline.conflict_detector import process_claim, log_claim_processing_result
        for claim in claims:
            try:
                result = await process_claim(claim, bq)
                log_claim_processing_result(result)
            except Exception as e:
                logger.error(f"Conflict detector error on claim {claim.claim_id}: {e}")

        claims_dicts = [c.model_dump(mode='json') for c in claims]
        resolved_doc_type = extracted_data.get("doc_type", doc_type_hint or "UNKNOWN")
        
        proposal_payload = {
            "file_id": file_id,
            "filename": file.filename,
            "extraction": extracted_data,
            "actions": [
                {"type": "CREATE_DOCUMENT", "params": {"doc_type": resolved_doc_type}},
                {"type": "APPLY_CLAIMS", "params": {"claims": claims_dicts}}
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
            proposed_actions=proposal_payload["actions"],
            extracted_claims=claims_dicts
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
