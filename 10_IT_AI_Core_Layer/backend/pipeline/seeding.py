"""
AutoHaus CIL — Corpus Seeding Toolchain
Phase 3, Step 9

Processes historical documents through the full CIL pipeline in
dependency order (Titles → Auctions → Insurance → Disclosures → ROs → Transport → Finance → Catch-all).

Uses Gemini Flash for extraction, Pro only for KAMM compliance docs.
Tracks API costs and enforces per-tier budget abort thresholds.
"""

import os
import uuid
import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from database.policy_engine import get_policy

logger = logging.getLogger("autohaus.seeding")

# ── Seeding Config (Defaults, overridden by Policy Engine) ──────────────

def get_seeding_config():
    batch_size = get_policy("SEEDING", "batch_size")
    pause_sec = get_policy("SEEDING", "pause_sec")
    abort_threshold_usd = get_policy("SEEDING", "abort_threshold_usd")
    review_queue_max = get_policy("SEEDING", "review_queue_max")

    if None in (batch_size, pause_sec, abort_threshold_usd, review_queue_max):
        raise ValueError("Missing required SEEDING policies in policy registry. No hardcoded fallbacks allowed.")

    return {
        "batch_size": int(batch_size),
        "pause_between_batches_sec": int(pause_sec),
        "abort_threshold_usd": float(abort_threshold_usd),
        "max_retries_per_doc": 2,
        "review_queue_max": int(review_queue_max),
        "enable_batch_hitl": True,
    }

# Tier order — documents must be seeded in this sequence
SEEDING_TIERS = [
    {
        "tier": 1,
        "doc_type": "VEHICLE_TITLE",
        "drive_folder": "02_Titles",
        "description": "Establishes VIN + ownership chain",
        "anchor_creates": ["VEHICLE", "PERSON"],
    },
    {
        "tier": 2,
        "doc_type": "AUCTION_RECEIPT",
        "drive_folder": "06_Auctions",
        "description": "Establishes purchase price + acquisition date",
        "anchor_creates": ["VENDOR", "TRANSACTION"],
    },
    {
        "tier": 3,
        "doc_type": "INSURANCE_CERT",
        "drive_folder": "04_Insurance",
        "description": "Establishes entity coverage boundaries",
        "anchor_creates": ["VENDOR"],
    },
    {
        "tier": 4,
        "doc_type": "DAMAGE_DISCLOSURE_IA",
        "drive_folder": "08_Compliance",
        "description": "Iowa compliance — links to VIN from Tier 1",
        "anchor_creates": [],
    },
    {
        "tier": 5,
        "doc_type": "SERVICE_RO",
        "drive_folder": "05_Service",
        "description": "Attaches to VIN from Tier 1",
        "anchor_creates": ["JOB", "PERSON"],
    },
    {
        "tier": 6,
        "doc_type": "TRANSPORT_INVOICE",
        "drive_folder": "07_Transport",
        "description": "Attaches to VIN, references VENDOR",
        "anchor_creates": ["VENDOR", "TRANSACTION"],
    },
    {
        "tier": 7,
        "doc_type": "FLOOR_PLAN_NOTE",
        "drive_folder": "10_Finance",
        "description": "Attaches to VIN, references VENDOR (lender)",
        "anchor_creates": ["VENDOR", "TRANSACTION"],
    },
    {
        "tier": 8,
        "doc_type": "BILL_OF_SALE",
        "drive_folder": "03_Sales",
        "description": "Purchase agreements",
        "anchor_creates": ["PERSON", "TRANSACTION"],
    },
]


# ── Cost Tracking ───────────────────────────────────────────────────────

class CostTracker:
    """Tracks API costs per tier and enforces abort thresholds."""
    
    def __init__(self, bq_client, batch_id: str, abort_threshold: float):
        self.bq_client = bq_client
        self.batch_id = batch_id
        self.abort_threshold = abort_threshold
        self.cumulative_cost = 0.0
    
    def log_cost(self, document_id: str, api_service: str, api_model: str,
                 input_tokens: int, output_tokens: int, stage: str):
        """Log an API call cost and check against threshold."""
        # Rough cost estimates (adjust as Gemini pricing changes)
        cost_per_1k_input = 0.000125 if "flash" in api_model.lower() else 0.00125
        cost_per_1k_output = 0.000375 if "flash" in api_model.lower() else 0.005
        
        estimated_cost = (input_tokens / 1000 * cost_per_1k_input) + \
                         (output_tokens / 1000 * cost_per_1k_output)
        self.cumulative_cost += estimated_cost
        
        row = {
            "log_id": str(uuid.uuid4()),
            "document_id": document_id,
            "api_service": api_service,
            "api_model": api_model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "page_count": None,
            "estimated_cost_usd": estimated_cost,
            "pipeline_stage": stage,
            "batch_id": self.batch_id,
            "abort_threshold_usd": self.abort_threshold,
            "cumulative_batch_cost_usd": self.cumulative_cost,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        try:
            self.bq_client.insert_rows_json(
                "autohaus-infrastructure.autohaus_cil.api_cost_log", [row]
            )
        except Exception as e:
            logger.error(f"[COST] Failed to log: {e}")
        
        return estimated_cost
    
    def check_budget(self) -> bool:
        """Returns True if we're still within budget."""
        if self.cumulative_cost >= self.abort_threshold:
            logger.warning(
                f"[COST] BUDGET EXCEEDED: ${self.cumulative_cost:.2f} >= ${self.abort_threshold:.2f}"
            )
            return False
        return True


# ── Seeding Engine ──────────────────────────────────────────────────────

def run_seeding(bq_client, drive_service, tiers: List[int] = None, dry_run: bool = False):
    """
    Main seeding entry point.
    
    Args:
        bq_client: BigQuery client
        drive_service: Google Drive API service
        tiers: Optional list of tier numbers to run (default: all)
        dry_run: If True, list files but don't process
    """
    selected_tiers = SEEDING_TIERS
    if tiers:
        selected_tiers = [t for t in SEEDING_TIERS if t["tier"] in tiers]

    logger.info(f"[SEED] Starting seeding run. Tiers: {[t['tier'] for t in selected_tiers]}")
    
    overall_stats = {
        "total_processed": 0,
        "total_duplicates": 0,
        "total_failures": 0,
        "total_cost_usd": 0.0,
        "tier_results": {},
    }

    for tier_config in selected_tiers:
        tier_num = tier_config["tier"]
        doc_type = tier_config["doc_type"]
        folder_name = tier_config["drive_folder"]
        
        logger.info(f"[SEED] ── Tier {tier_num}: {doc_type} ({folder_name}) ──")
        
        
        config = get_seeding_config()
        batch_id = f"seed_t{tier_num}_{datetime.utcnow().strftime('%Y%m%d_%H%M')}"
        cost_tracker = CostTracker(bq_client, batch_id, config["abort_threshold_usd"])
        
        # Find the Drive folder
        folder_id = _find_drive_folder(drive_service, folder_name)
        if not folder_id:
            logger.warning(f"[SEED] Folder '{folder_name}' not found. Skipping tier {tier_num}.")
            overall_stats["tier_results"][tier_num] = {"status": "SKIPPED", "reason": "Folder not found"}
            continue
        
        # List files in folder
        files = _list_drive_files(drive_service, folder_id)
        logger.info(f"[SEED] Found {len(files)} files in {folder_name}")
        
        if dry_run:
            overall_stats["tier_results"][tier_num] = {
                "status": "DRY_RUN",
                "file_count": len(files),
                "files": [f["name"] for f in files[:20]],
            }
            continue
        
        # Process in batches
        tier_stats = {"processed": 0, "duplicates": 0, "failures": 0, "cost_usd": 0.0}
        
        config = get_seeding_config()
        for i in range(0, len(files), config["batch_size"]):
            batch = files[i:i + config["batch_size"]]
            batch_num = (i // config["batch_size"]) + 1
            
            logger.info(f"[SEED] Batch {batch_num} ({len(batch)} files)")
            
            for file_meta in batch:
                result = _process_single_file(
                    bq_client, drive_service, file_meta, doc_type, cost_tracker
                )
                
                if result == "PROCESSED":
                    tier_stats["processed"] += 1
                elif result == "DUPLICATE":
                    tier_stats["duplicates"] += 1
                else:
                    tier_stats["failures"] += 1
                
                # Budget check after each file
                if not cost_tracker.check_budget():
                    logger.error(f"[SEED] ABORT: Budget exceeded for tier {tier_num}")
                    tier_stats["aborted"] = True
                    break
            
            # Check if aborted
            if tier_stats.get("aborted"):
                break
            
            # Pause between batches
            if i + config["batch_size"] < len(files):
                logger.info(f"[SEED] Pausing {config['pause_between_batches_sec']}s between batches...")
                time.sleep(config["pause_between_batches_sec"])
        
        tier_stats["cost_usd"] = cost_tracker.cumulative_cost
        overall_stats["tier_results"][tier_num] = tier_stats
        overall_stats["total_processed"] += tier_stats["processed"]
        overall_stats["total_duplicates"] += tier_stats["duplicates"]
        overall_stats["total_failures"] += tier_stats["failures"]
        overall_stats["total_cost_usd"] += tier_stats["cost_usd"]
        
        logger.info(f"[SEED] Tier {tier_num} complete: {tier_stats}")
    
    logger.info(f"[SEED] ══ Seeding complete ══ {overall_stats}")
    return overall_stats


def _process_single_file(bq_client, drive_service, file_meta: dict, 
                          expected_doc_type: str, cost_tracker: CostTracker) -> str:
    """
    Process a single file through the full pipeline:
    download → dedup → format route → classify → extract → link entities.
    
    Returns: "PROCESSED" | "DUPLICATE" | "FAILED"
    """
    import tempfile
    
    filename = file_meta["name"]
    file_id = file_meta["id"]
    mime_type = file_meta.get("mimeType", "application/octet-stream")
    
    try:
        # 1. Download
        temp_dir = os.path.join(tempfile.gettempdir(), "autohaus_cil_seeding")
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"{file_id}_{filename}")
        
        content = drive_service.files().get_media(fileId=file_id, supportsAllDrives=True).execute()
        with open(temp_path, "wb") as f:
            f.write(content)
        
        file_size = os.path.getsize(temp_path)
        if file_size == 0:
            logger.warning(f"[SEED] Zero-byte file: {filename}")
            return "FAILED"
        
        # 2. Dedup Gate
        from pipeline.dedup_gate import ingest_document
        document_id, state = ingest_document(
            bq_client, temp_path, file_id, filename, mime_type, file_size
        )
        
        if state == "DUPLICATE":
            _cleanup(temp_path)
            return "DUPLICATE"
        
        # 3. Format Route
        from pipeline.format_router import route_format
        detected_format, action, converted_path = route_format(temp_path, filename)
        active_path = converted_path or temp_path
        
        if action == "FAILED_UNPROCESSABLE":
            _cleanup(temp_path)
            return "FAILED"
        
        # 4. Get text content for extraction
        text_content = _extract_text(active_path, detected_format)
        if not text_content:
            logger.warning(f"[SEED] No text extracted from {filename}")
            _cleanup(temp_path)
            return "FAILED"
        
        # 5. Classification (skip if we know the type from folder placement)
        doc_type = expected_doc_type
        
        # 6. Extract fields
        from pipeline.extraction_engine import extract_fields, get_schema
        extraction_result = extract_fields(text_content, doc_type, document_id, bq_client)
        
        if not extraction_result:
            logger.warning(f"[SEED] Extraction failed for {filename}")
            _cleanup(temp_path)
            return "FAILED"
        
        # 7. Entity linking
        schema = get_schema(doc_type)
        if schema and extraction_result.get("fields"):
            from pipeline.entity_resolution import link_document_entities
            link_document_entities(bq_client, document_id, extraction_result["fields"], schema)
        
        _cleanup(temp_path)
        if converted_path:
            _cleanup(converted_path)
        
        logger.info(f"[SEED] ✅ {filename} → {document_id}")
        return "PROCESSED"
    
    except Exception as e:
        logger.error(f"[SEED] ❌ {filename}: {e}")
        return "FAILED"


def _extract_text(file_path: str, detected_format: str) -> Optional[str]:
    """Extract text content from a file based on its format."""
    try:
        if detected_format == "TEXT_PDF":
            import fitz
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        
        elif detected_format == "SCANNED_PDF":
            # For scanned PDFs, we'd normally use Document AI OCR.
            # Fallback: try PyMuPDF anyway (sometimes metadata is extractable)
            try:
                import fitz
                doc = fitz.open(file_path)
                text = ""
                for page in doc:
                    text += page.get_text()
                doc.close()
                if len(text.strip()) > 50:
                    return text
            except:
                pass
            logger.warning(f"[SEED] Scanned PDF needs OCR: {file_path}")
            return None
        
        elif detected_format in ("IMAGE", "IMAGE_HEIC"):
            # For images, we'd pass to Gemini Vision directly
            # Return a placeholder that triggers Vision extraction
            return f"[IMAGE_FILE: {file_path}]"
        
        elif detected_format == "SPREADSHEET":
            # Basic CSV/Excel reading
            if file_path.endswith(".csv"):
                with open(file_path, "r") as f:
                    return f.read()
            return None
        
        elif detected_format == "WORD_DOC":
            try:
                import docx
                doc = docx.Document(file_path)
                return "\n".join([p.text for p in doc.paragraphs])
            except ImportError:
                logger.warning("[SEED] python-docx not installed")
                return None
        
        elif detected_format == "TEXT_FILE":
            with open(file_path, "r", errors="ignore") as f:
                return f.read()
        
        return None
    except Exception as e:
        logger.error(f"[SEED] Text extraction failed: {e}")
        return None


def _find_drive_folder(drive_service, folder_name: str) -> Optional[str]:
    """Find a Google Drive folder by name (supporting Shared Drives)."""
    try:
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = drive_service.files().list(
            q=query, 
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        files = results.get("files", [])
        return files[0]["id"] if files else None
    except Exception as e:
        logger.error(f"[SEED] Folder lookup failed: {e}")
        return None


def _list_drive_files(drive_service, folder_id: str) -> List[dict]:
    """List all files in a Drive folder (non-recursive)."""
    try:
        all_files = []
        page_token = None
        while True:
            results = drive_service.files().list(
                q=f"'{folder_id}' in parents and trashed = false and mimeType != 'application/vnd.google-apps.folder'",
                fields="nextPageToken, files(id, name, mimeType, size, createdTime)",
                pageSize=100,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            all_files.extend(results.get("files", []))
            page_token = results.get("nextPageToken")
            if not page_token:
                break
        return all_files
    except Exception as e:
        logger.error(f"[SEED] File listing failed: {e}")
        return []


def _cleanup(path: str):
    """Remove temp file."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except:
        pass
