"""
AutoHaus CIL — Pipeline Queue & Worker
Phase 1, Step 3

Pragmatic approach: Uses FastAPI's built-in asyncio task queue.
This is NOT Pub/Sub + Cloud Tasks — it's a lightweight in-process queue
that handles the current volume. The interface is designed so swapping
to Cloud Tasks later requires changing only this file.

Responsibilities:
1. Accept a file detection event from DriveEar
2. Download the file to a temp directory
3. Run stability check (file size not changing = upload complete)
4. Pass to dedup_gate.ingest_document()
5. If INGESTED, continue pipeline (format router in Step 4)
6. If DUPLICATE, stop and log
7. On failure, write to processing_failures with retry tracking
"""

import os
import io
import uuid
import json
import asyncio
import logging
import tempfile
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("autohaus.pipeline_queue")

# In-memory tracking for the lightweight queue
_active_jobs = {}  # job_id -> status
_retry_delays = [10, 30, 90]  # seconds — exponential-ish backoff


class PipelineJob:
    """Represents a single document processing job."""
    def __init__(self, drive_file_id: str, filename: str, mime_type: str, byte_size: int):
        self.job_id = str(uuid.uuid4())
        self.drive_file_id = drive_file_id
        self.filename = filename
        self.mime_type = mime_type
        self.byte_size = byte_size
        self.retry_count = 0
        self.max_retries = 3
        self.status = "QUEUED"  # QUEUED | PROCESSING | COMPLETED | FAILED | DUPLICATE
        self.document_id: Optional[str] = None
        self.error: Optional[str] = None
        self.created_at = datetime.utcnow()


async def enqueue_file(drive_service, bq_client, file_metadata: dict) -> str:
    """
    Main entry point called by DriveEar when a new file is detected.
    Downloads the file, runs the dedup gate, and returns the job status.
    
    Returns job_id for tracking.
    """
    job = PipelineJob(
        drive_file_id=file_metadata["id"],
        filename=file_metadata["name"],
        mime_type=file_metadata.get("mimeType", "application/octet-stream"),
        byte_size=int(file_metadata.get("size", 0)),
    )
    _active_jobs[job.job_id] = job
    
    logger.info(f"[QUEUE] Job {job.job_id} created for file: {job.filename}")
    
    # Run the pipeline worker as a background task
    asyncio.create_task(_process_job(drive_service, bq_client, job))
    
    return job.job_id


async def _process_job(drive_service, bq_client, job: PipelineJob):
    """
    The actual worker that processes a single document through the pipeline.
    Runs as an async background task.
    """
    job.status = "PROCESSING"
    
    try:
        # Step 1: Stability check — verify the file isn't still uploading
        stable = await _check_file_stability(drive_service, job.drive_file_id)
        if not stable:
            job.status = "FAILED"
            job.error = "FILE_UNSTABLE: File size still changing (upload in progress?)"
            await _record_failure(bq_client, job, "STABILITY_CHECK", "FILE_UNSTABLE", job.error)
            return

        # Step 2: Download file to temp directory
        temp_path = await _download_file(drive_service, job.drive_file_id, job.filename)
        if not temp_path:
            job.status = "FAILED"
            job.error = "DOWNLOAD_FAILED"
            await _record_failure(bq_client, job, "DOWNLOAD", "DOWNLOAD_FAILED", "Could not download file from Drive")
            return

        # Step 3: Zero-byte check
        file_size = os.path.getsize(temp_path)
        if file_size == 0:
            job.status = "FAILED"
            job.error = "ZERO_BYTE_FILE"
            await _record_failure(bq_client, job, "VALIDATION", "ZERO_BYTE", "File is 0 bytes")
            _cleanup_temp(temp_path)
            return

        # Step 4: Run through Dedup Gate
        from pipeline.dedup_gate import ingest_document
        
        document_id, terminal_state = ingest_document(
            bq_client=bq_client,
            file_path=temp_path,
            drive_file_id=job.drive_file_id,
            filename_original=job.filename,
            detected_format=job.mime_type,
            byte_size=file_size,
        )
        
        job.document_id = document_id
        
        if terminal_state == "DUPLICATE":
            job.status = "DUPLICATE"
            logger.info(f"[QUEUE] Job {job.job_id} → DUPLICATE of {document_id}")
            _cleanup_temp(temp_path)
        else:
            logger.info(f"[QUEUE] Job {job.job_id} → INGESTED as {document_id}. Running Format Router...")
            
            # Step 5: Format Router — determine true file type and route
            from pipeline.format_router import route_format, emit_format_routed_event
            
            detected_format, terminal_action, converted_path = route_format(temp_path, job.filename)
            
            # Use converted file path if conversion happened (e.g., HEIC → JPEG)
            active_path = converted_path or temp_path
            
            # Emit FORMAT_ROUTED event
            emit_format_routed_event(bq_client, document_id, detected_format, terminal_action)
            
            if terminal_action == "FAILED_UNPROCESSABLE":
                job.status = "FAILED"
                job.error = f"FORMAT: {detected_format}"
                logger.warning(f"[QUEUE] Job {job.job_id} → FAILED_UNPROCESSABLE ({detected_format})")
                await _record_failure(bq_client, job, "FORMAT_ROUTE", detected_format, f"Unprocessable format: {detected_format}")
            elif terminal_action == "UNKNOWN_FORMAT":
                job.status = "COMPLETED"  # Document is registered but needs review
                logger.warning(f"[QUEUE] Job {job.job_id} → UNKNOWN_FORMAT ({detected_format}). Plate will be generated.")
                # TODO (Pass 5): Generate REVIEW_REQUIRED plate for unknown formats
            else:
                # -- PHASE 5: EXTRACTION & KNOWLEDGE LINKING --
                from pipeline.ocr_engine import extract_text_from_file
                from pipeline.extraction_engine import classify_document, extract_fields, get_schema
                from pipeline.version_governor import process_version_grouping
                from pipeline.entity_resolution import link_document_entities
                
                # 1. OCR / Text Extraction
                text_content = await extract_text_from_file(active_path, detected_format)
                if not text_content:
                     logger.error(f"[PIPELINE] Failed to extract text for {document_id}")
                     await _record_failure(bq_client, job, "OCR", "TEXT_EXTRACTION_FAILED", "No text extracted from file")
                     return

                # 2. Classification (if unknown)
                doc_type, class_conf = classify_document(text_content)
                logger.info(f"[PIPELINE] Classifed {document_id} as {doc_type} (conf: {class_conf})")
                
                # Update document with type
                _update_doc_type(bq_client, document_id, doc_type, class_conf)

                # 3. Field Extraction
                extraction_result = extract_fields(text_content, doc_type, document_id, bq_client)
                if not extraction_result:
                    logger.error(f"[PIPELINE] Extraction failed for {document_id}")
                    await _record_failure(bq_client, job, "EXTRACTION", "FIELD_EXTRACTION_FAILED", "Gemini returned no results")
                else:
                    fields = extraction_result["fields"]
                    vin = fields.get("vin", {}).get("value")
                    
                    # 4. Version Grouping
                    group_meta = process_version_grouping(bq_client, document_id, doc_type, vin, text_content)
                    logger.info(f"[PIPELINE] Versioning: {group_meta}")

                    # 5. Entity Linking & Enrichment
                    schema = get_schema(doc_type)
                    if schema:
                        links = link_document_entities(bq_client, document_id, fields, schema)
                        logger.info(f"[PIPELINE] Created {len(links)} links for {document_id}")

                # Emit INGESTION_RUN_COMPLETED event (receipt)
                try:
                    event_id = str(uuid.uuid4())
                    event_row = {
                        "event_id": event_id,
                        "event_type": "INGESTION_RUN_COMPLETED",
                        "timestamp": datetime.utcnow().isoformat(),
                        "actor_type": "SYSTEM",
                        "actor_id": "queue_worker",
                        "actor_role": "ADMIN",
                        "target_type": "DOCUMENT",
                        "target_id": document_id,
                        "payload": json.dumps({
                            "total_files_processed": 1,
                            "total_bytes": job.byte_size,
                            "average_latency_ms": int((datetime.utcnow() - job.created_at).total_seconds() * 1000),
                            "doc_type": doc_type
                        }),
                        "metadata": None,
                        "idempotency_key": f"ingest_{job.job_id}"
                    }
                    bq_client.insert_rows_json("autohaus-infrastructure.autohaus_cil.cil_events", [event_row])
                    logger.info(f"[LEDGER] Ingestion receipt emitted: {event_id}")
                except Exception as e:
                    logger.warning(f"[LEDGER] Failed to emit ingestion receipt: {e}")
            
            _cleanup_temp(temp_path)
            if converted_path and converted_path != temp_path:
                _cleanup_temp(converted_path)

    except Exception as e:
        logger.error(f"[QUEUE] Job {job.job_id} FAILED: {e}")
        job.error = str(e)
        
        # Retry logic
        if job.retry_count < job.max_retries:
            job.retry_count += 1
            delay = _retry_delays[min(job.retry_count - 1, len(_retry_delays) - 1)]
            logger.info(f"[QUEUE] Retrying job {job.job_id} in {delay}s (attempt {job.retry_count}/{job.max_retries})")
            await asyncio.sleep(delay)
            await _process_job(drive_service, bq_client, job)
        else:
            job.status = "FAILED"
            await _record_failure(bq_client, job, "PIPELINE", "MAX_RETRIES_EXCEEDED", str(e))


async def _check_file_stability(drive_service, file_id: str, wait_seconds: int = 10) -> bool:
    """
    Poll file size twice with a gap to confirm the upload is complete.
    Returns True if file is stable (same size both times).
    """
    try:
        meta1 = drive_service.files().get(fileId=file_id, fields="size").execute()
        size1 = int(meta1.get("size", 0))
        
        await asyncio.sleep(wait_seconds)
        
        meta2 = drive_service.files().get(fileId=file_id, fields="size").execute()
        size2 = int(meta2.get("size", 0))
        
        if size1 != size2:
            logger.warning(f"[STABILITY] File {file_id} size changed: {size1} → {size2}")
            return False
        return True
    except Exception as e:
        logger.error(f"[STABILITY] Check failed for {file_id}: {e}")
        return False


async def _download_file(drive_service, file_id: str, filename: str) -> Optional[str]:
    """
    Download a file from Google Drive to a temporary directory.
    Returns the local temp file path, or None on failure.
    """
    try:
        # Create a temp directory specific to CIL processing
        temp_dir = os.path.join(tempfile.gettempdir(), "autohaus_cil_pipeline")
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_path = os.path.join(temp_dir, f"{file_id}_{filename}")
        
        request = drive_service.files().get_media(fileId=file_id)
        content = request.execute()
        
        with open(temp_path, "wb") as f:
            f.write(content)
        
        logger.info(f"[DOWNLOAD] Saved {filename} to {temp_path} ({len(content)} bytes)")
        return temp_path
    except Exception as e:
        logger.error(f"[DOWNLOAD] Failed for {file_id}: {e}")
        return None


def _cleanup_temp(temp_path: str):
    """Remove temp file after processing."""
    try:
        if os.path.exists(temp_path):
            os.remove(temp_path)
    except Exception:
        pass


def _update_doc_type(bq_client, doc_id: str, doc_type: str, confidence: float):
    """Updates the document record with the classified doc_type."""
    from google.cloud import bigquery as bq
    query = """
        UPDATE `autohaus-infrastructure.autohaus_cil.documents`
        SET doc_type = @doc_type,
            classification_confidence = @conf
        WHERE document_id = @doc_id
    """
    params = [
        bq.ScalarQueryParameter("doc_type", "STRING", doc_type),
        bq.ScalarQueryParameter("conf", "FLOAT64", confidence),
        bq.ScalarQueryParameter("doc_id", "STRING", doc_id),
    ]
    try:
        bq_client.query(query, job_config=bq.QueryJobConfig(query_parameters=params)).result()
    except Exception as e:
        logger.error(f"[PIPELINE] Failed to update doc_type: {e}")


async def _record_failure(bq_client, job: PipelineJob, stage: str, error_type: str, error_message: Optional[str]):
    """Write a failure record to the processing_failures table."""
    try:
        row = {
            "failure_id": str(uuid.uuid4()),
            "document_id": job.document_id or job.drive_file_id,  # Use drive_file_id if no doc yet
            "pipeline_stage": stage,
            "error_type": error_type,
            "error_message": (error_message or "")[:500],  # Truncate long errors
            "retry_count": job.retry_count,
            "max_retries": job.max_retries,
            "next_retry_at": None,
            "resolved": job.retry_count >= job.max_retries,  # Resolved = gave up
            "resolved_at": datetime.utcnow().isoformat() if job.retry_count >= job.max_retries else None,
            "resolution_method": "ABANDONED" if job.retry_count >= job.max_retries else None,
            "created_at": datetime.utcnow().isoformat(),
        }
        
        table = "autohaus-infrastructure.autohaus_cil.processing_failures"
        errors = bq_client.insert_rows_json(table, [row])
        if errors:
            logger.error(f"[FAILURE LOG] Could not write failure record: {errors}")
    except Exception as e:
        logger.error(f"[FAILURE LOG] Exception writing failure: {e}")


def get_job_status(job_id: str) -> Optional[dict]:
    """Get the current status of a pipeline job."""
    job = _active_jobs.get(job_id)
    if not job:
        return None
    return {
        "job_id": job.job_id,
        "filename": job.filename,
        "status": job.status,
        "document_id": job.document_id,
        "retry_count": job.retry_count,
        "error": job.error,
        "created_at": job.created_at.isoformat(),
    }
