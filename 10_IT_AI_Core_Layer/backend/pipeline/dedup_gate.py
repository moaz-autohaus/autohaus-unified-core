"""
AutoHaus CIL — Document Ingestion & Deduplication Gate
Phase 1, Step 2

This module handles two critical functions:
1. SHA-256 content hashing of incoming files for deduplication
2. Checking BigQuery for existing documents with the same hash
3. Registering new documents and emitting the correct cil_event

Every document that enters the system passes through this gate FIRST.
If the hash already exists → DUPLICATE terminal state → pipeline stops.
If the hash is new → DOCUMENT_REGISTERED event → pipeline continues.
"""

import hashlib
import uuid
import logging
from datetime import datetime
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def compute_content_hash(file_path: str) -> str:
    """
    Compute SHA-256 hash of a file's contents.
    Reads in 8KB chunks to handle large files without memory issues.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def check_duplicate(bq_client, content_hash: str) -> Optional[dict]:
    """
    Check BigQuery documents table for an existing document with this content hash.
    Returns the existing document record if found, None if new.
    """
    from google.cloud import bigquery as bq

    query = """
        SELECT document_id, filename_original, terminal_state, ingested_at
        FROM `autohaus-infrastructure.autohaus_cil.documents`
        WHERE content_hash = @content_hash
        AND latest_version = TRUE
        LIMIT 1
    """
    job_config = bq.QueryJobConfig(
        query_parameters=[
            bq.ScalarQueryParameter("content_hash", "STRING", content_hash)
        ]
    )

    try:
        results = list(bq_client.query(query, job_config=job_config).result())
        if results:
            row = results[0]
            return {
                "document_id": row.document_id,
                "filename_original": row.filename_original,
                "terminal_state": row.terminal_state,
                "ingested_at": str(row.ingested_at),
            }
        return None
    except Exception as e:
        # If the table doesn't exist yet (first run), treat as no duplicate
        logger.warning(f"Duplicate check query failed (table may not exist yet): {e}")
        return None


def register_document(
    bq_client,
    file_path: str,
    content_hash: str,
    drive_file_id: str,
    filename_original: str,
    detected_format: str,
    byte_size: int,
) -> str:
    """
    Insert a new document record into BigQuery and emit a DOCUMENT_REGISTERED event.
    Returns the new document_id.
    """
    document_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # 1. Insert into documents table
    doc_row = {
        "document_id": document_id,
        "content_hash": content_hash,
        "filename_original": filename_original,
        "detected_format": detected_format,
        "drive_file_id": drive_file_id,
        "archive_path": None,  # Set later when filed to canonical folder
        "doc_type": None,  # Set in Pass 5 (Classification)
        "classification_confidence": None,
        "authority_level": "ADVISORY",
        "version": 1,
        "version_group_id": document_id,  # Self-referencing until version grouping runs
        "latest_version": True,
        "amendment_lock": False,
        "terminal_state": "INGESTED",
        "requires_human_review": False,
        "kamm_compliance_type": False,
        "ingested_at": now,
    }

    table_ref = "autohaus-infrastructure.autohaus_cil.documents"
    errors = bq_client.insert_rows_json(table_ref, [doc_row])
    if errors:
        logger.error(f"Failed to insert document row: {errors}")
        raise Exception(f"Document insert failed: {errors}")

    # 2. Emit DOCUMENT_REGISTERED event to cil_events
    event_row = {
        "event_id": str(uuid.uuid4()),
        "event_type": "DOCUMENT_REGISTERED",
        "timestamp": now,
        "actor_type": "SYSTEM",
        "actor_id": "pipeline_ingestion",
        "actor_role": "SYSTEM",
        "target_type": "DOCUMENT",
        "target_id": document_id,
        "payload": '{"drive_id": "' + drive_file_id + '", "content_hash": "' + content_hash + '", "mime": "' + detected_format + '"}',
        "metadata": None,
        "idempotency_key": f"doc_reg_{drive_file_id}_{content_hash}",
    }

    events_table = "autohaus-infrastructure.autohaus_cil.cil_events"
    errors = bq_client.insert_rows_json(events_table, [event_row])
    if errors:
        logger.error(f"Failed to insert DOCUMENT_REGISTERED event: {errors}")
        # Document is already inserted, so we log the error but don't fail hard
    else:
        logger.info(f"Document registered: {document_id} ({filename_original})")

    return document_id


def emit_duplicate_event(
    bq_client,
    content_hash: str,
    existing_document_id: str,
    drive_file_id: str,
) -> None:
    """
    When a duplicate is detected, emit a DUPLICATE_DETECTED event to cil_events.
    The document is NOT inserted into the documents table.
    """
    now = datetime.utcnow().isoformat()

    event_row = {
        "event_id": str(uuid.uuid4()),
        "event_type": "DUPLICATE_DETECTED",
        "timestamp": now,
        "actor_type": "SYSTEM",
        "actor_id": "pipeline_dedup_gate",
        "actor_role": "SYSTEM",
        "target_type": "DOCUMENT",
        "target_id": existing_document_id,
        "payload": '{"content_hash": "' + content_hash + '", "existing_document_id": "' + existing_document_id + '"}',
        "metadata": None,
        "idempotency_key": f"dup_{drive_file_id}_{content_hash}",
    }

    events_table = "autohaus-infrastructure.autohaus_cil.cil_events"
    errors = bq_client.insert_rows_json(events_table, [event_row])
    if errors:
        logger.error(f"Failed to insert DUPLICATE_DETECTED event: {errors}")
    else:
        logger.info(f"Duplicate detected: {drive_file_id} matches existing {existing_document_id}")


def ingest_document(
    bq_client,
    file_path: str,
    drive_file_id: str,
    filename_original: str,
    detected_format: str,
    byte_size: int,
) -> Tuple[str, str]:
    """
    Main entry point for document ingestion.
    
    Returns a tuple of (document_id_or_existing, terminal_state).
    
    Possible outcomes:
      - ("uuid-xxx", "INGESTED")  → New document, pipeline should continue.
      - ("uuid-existing", "DUPLICATE") → Exact duplicate, pipeline stops.
    """
    # Step 1: Hash the file
    content_hash = compute_content_hash(file_path)
    logger.info(f"Content hash for {filename_original}: {content_hash[:16]}...")

    # Step 2: Check for duplicates
    existing = check_duplicate(bq_client, content_hash)

    if existing:
        # DUPLICATE — emit event, do NOT register
        logger.info(
            f"DUPLICATE: {filename_original} matches existing document "
            f"{existing['document_id']} ({existing['filename_original']})"
        )
        emit_duplicate_event(
            bq_client,
            content_hash=content_hash,
            existing_document_id=existing["document_id"],
            drive_file_id=drive_file_id,
        )
        return existing["document_id"], "DUPLICATE"

    # Step 3: New document — register it
    document_id = register_document(
        bq_client,
        file_path=file_path,
        content_hash=content_hash,
        drive_file_id=drive_file_id,
        filename_original=filename_original,
        detected_format=detected_format,
        byte_size=byte_size,
    )
    return document_id, "INGESTED"
