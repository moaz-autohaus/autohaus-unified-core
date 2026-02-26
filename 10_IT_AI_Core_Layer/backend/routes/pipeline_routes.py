"""
AutoHaus CIL — Pipeline API Routes
Provides endpoints for:
- Manual document ingestion trigger
- Job status checking
- Pipeline health
"""

import json
import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any

logger = logging.getLogger("autohaus.pipeline_routes")

pipeline_router = APIRouter(tags=["Pipeline"])


class IngestRequest(BaseModel):
    """Manual ingestion trigger for testing or admin use."""
    drive_file_id: str
    filename: str
    mime_type: str = "application/octet-stream"
    byte_size: int = 0


class RenderErrorRequest(BaseModel):
    """Payload for reporting UI rendering failures."""
    plate_type: str
    reason: str
    payload_snapshot_hash: str
    target_id: str  # Document or Entity ID


@pipeline_router.post("/pipeline/ingest")
async def trigger_ingest(request: IngestRequest):
    """
    Manually trigger document ingestion for a Drive file.
    Useful for testing or re-processing a specific file.
    """
    try:
        from pipeline.queue_worker import enqueue_file
        from services.drive_ear import drive_ear
        from database.bigquery_client import BigQueryClient
        
        bq = BigQueryClient()
        
        if not drive_ear.service:
            raise HTTPException(status_code=503, detail="Drive service not initialized. Check GCP credentials.")
        
        file_metadata = {
            "id": request.drive_file_id,
            "name": request.filename,
            "mimeType": request.mime_type,
            "size": str(request.byte_size),
        }
        
        job_id = await enqueue_file(drive_ear.service, bq.client, file_metadata)
        
        return {
            "status": "queued",
            "job_id": job_id,
            "message": f"File '{request.filename}' queued for processing."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingest trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@pipeline_router.get("/pipeline/job/{job_id}")
async def get_job(job_id: str):
    """Check the status of a pipeline job."""
    from pipeline.queue_worker import get_job_status
    
    status = get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return status


@pipeline_router.get("/pipeline/health")
async def pipeline_health():
    """Quick health check for the pipeline subsystem."""
    from pipeline.queue_worker import _active_jobs
    
    total = len(_active_jobs)
    by_status = {}
    for job in _active_jobs.values():
        by_status[job.status] = by_status.get(job.status, 0) + 1
    
    return {
        "status": "operational",
        "total_jobs_tracked": total,
        "jobs_by_status": by_status,
    }


@pipeline_router.post("/events/render-error")
async def log_render_error(error: RenderErrorRequest):
    """
    Log a UI_RENDER_FAILED event to the system ledger.
    """
    try:
        from database.bigquery_client import BigQueryClient
        bq = BigQueryClient()
        
        event_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        event_row = {
            "event_id": event_id,
            "event_type": "UI_RENDER_FAILED",
            "timestamp": now,
            "actor_type": "SYSTEM",
            "actor_id": "CHIEF_OF_STAFF_UI",
            "actor_role": "SYSTEM",
            "target_type": "DOCUMENT",
            "target_id": error.target_id,
            "payload": json.dumps({
                "plate_type": error.plate_type,
                "reason": error.reason,
                "hash": error.payload_snapshot_hash
            }),
            "metadata": None,
            "idempotency_key": f"render_fail_{event_id}"
        }
        
        errors = bq.client.insert_rows_json(
            "autohaus-infrastructure.autohaus_cil.cil_events", [event_row]
        )
        
        if errors:
            logger.error(f"[LEDGER] Failed to log render error: {errors}")
            raise HTTPException(status_code=500, detail="Ledger write failed")
            
        return {"status": "event_logged", "event_id": event_id}
    except Exception as e:
        logger.error(f"Render error logging failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
