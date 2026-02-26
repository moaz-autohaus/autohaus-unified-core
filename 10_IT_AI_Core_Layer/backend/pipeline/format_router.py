"""
AutoHaus CIL — Format Router
Phase 1, Step 4

Determines the true file type of an incoming document and routes it
to the correct processing pipeline. Uses python-magic for MIME detection
and PyMuPDF for PDF text-vs-scanned classification.

Supported Routes:
  TEXT_PDF        → Direct text extraction (no OCR needed)
  SCANNED_PDF     → Needs OCR via Document AI
  IMAGE           → Gemini Vision
  IMAGE_HEIC      → Convert to JPEG first, then Gemini Vision
  VIDEO           → Frame extraction + Vision (params TBD)
  AUDIO           → Gemini audio transcription (params TBD)
  SPREADSHEET     → Structured parser → BigQuery direct
  WORD_DOC        → Text extraction
  EMAIL           → Header + body parse
  UNKNOWN_FORMAT  → Terminal state, generates REVIEW_REQUIRED plate

Security exceptions:
  PASSWORD_PROTECTED → FAILED_UNPROCESSABLE
  EXECUTABLE         → UNKNOWN_FORMAT + security alert
  ZERO_BYTE          → FAILED_UNPROCESSABLE (caught earlier in queue_worker)
"""

import os
import uuid
import json
import logging
from datetime import datetime
from typing import Tuple, Optional

logger = logging.getLogger("autohaus.format_router")

# ---------------------------------------------------------------------------
# MIME → Route mapping
# ---------------------------------------------------------------------------
ROUTE_MAP = {
    # PDFs handled specially (text vs scanned detection)
    "application/pdf": "_route_pdf",
    
    # Images
    "image/jpeg": "IMAGE",
    "image/png": "IMAGE",
    "image/gif": "IMAGE",
    "image/tiff": "IMAGE",
    "image/webp": "IMAGE",
    "image/heic": "IMAGE_HEIC",
    "image/heif": "IMAGE_HEIC",
    
    # Video
    "video/mp4": "VIDEO",
    "video/quicktime": "VIDEO",
    "video/x-msvideo": "VIDEO",
    "video/webm": "VIDEO",
    
    # Audio
    "audio/mpeg": "AUDIO",
    "audio/mp4": "AUDIO",
    "audio/ogg": "AUDIO",
    "audio/wav": "AUDIO",
    "audio/x-wav": "AUDIO",
    
    # Spreadsheets
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "SPREADSHEET",
    "application/vnd.ms-excel": "SPREADSHEET",
    "text/csv": "SPREADSHEET",
    
    # Word documents
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "WORD_DOC",
    "application/msword": "WORD_DOC",
    
    # Email
    "message/rfc822": "EMAIL",
    
    # Plain text (could be notes, logs)
    "text/plain": "TEXT_FILE",
}

# Files that should NEVER be processed — security concern
BLOCKED_MIMES = {
    "application/x-executable",
    "application/x-msdos-program",
    "application/x-msdownload",
    "application/x-dosexec",
}

BLOCKED_EXTENSIONS = {".exe", ".bat", ".cmd", ".com", ".msi", ".scr", ".ps1", ".sh"}


def detect_mime(file_path: str) -> str:
    """
    Detect the true MIME type of a file using python-magic.
    Falls back to extension-based detection if magic isn't available.
    """
    try:
        import magic
        mime = magic.from_file(file_path, mime=True)
        return mime
    except ImportError:
        logger.warning("[FORMAT] python-magic not installed. Falling back to extension-based detection.")
        return _mime_from_extension(file_path)
    except Exception as e:
        logger.error(f"[FORMAT] Magic detection failed: {e}")
        return _mime_from_extension(file_path)


def _mime_from_extension(file_path: str) -> str:
    """Fallback MIME detection based on file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    ext_map = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".heic": "image/heic",
        ".heif": "image/heif",
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".csv": "text/csv",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".eml": "message/rfc822",
        ".txt": "text/plain",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
    }
    return ext_map.get(ext, "application/octet-stream")


def _is_pdf_scanned(file_path: str) -> bool:
    """
    Determine if a PDF is scanned (image-based) or has extractable text.
    Uses PyMuPDF (fitz). If less than 50 characters extracted, it's scanned.
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        total_text = ""
        for page in doc:
            total_text += page.get_text()
        doc.close()
        return len(total_text.strip()) < 50
    except ImportError:
        logger.warning("[FORMAT] PyMuPDF not installed. Treating all PDFs as scanned (safer — will OCR).")
        return True
    except Exception as e:
        logger.error(f"[FORMAT] PDF text check failed: {e}. Treating as scanned.")
        return True


def _is_pdf_password_protected(file_path: str) -> bool:
    """Check if a PDF is password-protected."""
    try:
        import fitz
        doc = fitz.open(file_path)
        is_encrypted = doc.is_encrypted
        doc.close()
        return is_encrypted
    except ImportError:
        # Can't check — assume not protected
        return False
    except Exception:
        return False


def convert_heic_to_jpeg(heic_path: str) -> Optional[str]:
    """
    Convert HEIC/HEIF image to JPEG for Gemini Vision compatibility.
    Returns the path to the converted JPEG, or None on failure.
    """
    try:
        from PIL import Image
        import pillow_heif
        pillow_heif.register_heif_opener()
        
        img = Image.open(heic_path)
        jpeg_path = heic_path.rsplit(".", 1)[0] + ".jpg"
        img.save(jpeg_path, "JPEG", quality=95)
        logger.info(f"[FORMAT] Converted HEIC → JPEG: {jpeg_path}")
        return jpeg_path
    except ImportError:
        logger.error("[FORMAT] pillow-heif not installed. Cannot convert HEIC files.")
        return None
    except Exception as e:
        logger.error(f"[FORMAT] HEIC conversion failed: {e}")
        return None


def route_format(file_path: str, filename_original: str = "") -> Tuple[str, str, Optional[str]]:
    """
    Main entry point for the Format Router.
    
    Args:
        file_path: Path to the downloaded file on disk.
        filename_original: Original filename for extension fallback.
        
    Returns:
        Tuple of (detected_format, terminal_action, converted_path)
        
        detected_format: One of the route types (TEXT_PDF, SCANNED_PDF, IMAGE, etc.)
        terminal_action: "CONTINUE" | "FAILED_UNPROCESSABLE" | "UNKNOWN_FORMAT"
        converted_path: Path to converted file if conversion happened (e.g., HEIC→JPEG), else None
    """
    # Step 1: Security check on extension
    ext = os.path.splitext(filename_original or file_path)[1].lower()
    if ext in BLOCKED_EXTENSIONS:
        logger.warning(f"[FORMAT] BLOCKED: Executable file detected: {filename_original}")
        return "EXECUTABLE", "UNKNOWN_FORMAT", None
    
    # Step 2: Detect true MIME type
    mime = detect_mime(file_path)
    logger.info(f"[FORMAT] Detected MIME: {mime} for {filename_original}")
    
    # Step 3: Security check on MIME
    if mime in BLOCKED_MIMES:
        logger.warning(f"[FORMAT] BLOCKED: Dangerous MIME type {mime}: {filename_original}")
        return "EXECUTABLE", "UNKNOWN_FORMAT", None
    
    # Step 4: Route based on MIME
    route = ROUTE_MAP.get(mime)
    
    if route is None:
        logger.warning(f"[FORMAT] Unknown MIME type {mime} for {filename_original}")
        return "UNKNOWN", "UNKNOWN_FORMAT", None
    
    # Step 5: Special handling for PDFs
    if route == "_route_pdf":
        # Check password protection first
        if _is_pdf_password_protected(file_path):
            logger.warning(f"[FORMAT] Password-protected PDF: {filename_original}")
            return "PASSWORD_PROTECTED_PDF", "FAILED_UNPROCESSABLE", None
        
        # Determine text vs scanned
        if _is_pdf_scanned(file_path):
            return "SCANNED_PDF", "CONTINUE", None
        else:
            return "TEXT_PDF", "CONTINUE", None
    
    # Step 6: Special handling for HEIC
    if route == "IMAGE_HEIC":
        converted = convert_heic_to_jpeg(file_path)
        if converted:
            return "IMAGE", "CONTINUE", converted
        else:
            return "IMAGE_HEIC", "UNKNOWN_FORMAT", None
    
    # Step 7: Video and Audio — route but flag that params are TBD
    if route in ("VIDEO", "AUDIO"):
        logger.info(f"[FORMAT] {route} file detected. Processing params TBD — routing to REVIEW_REQUIRED.")
        return route, "CONTINUE", None
    
    # Step 8: Standard route
    return route, "CONTINUE", None


def emit_format_routed_event(bq_client, document_id: str, detected_format: str, routing_pipeline: str):
    """Emit a FORMAT_ROUTED event to cil_events."""
    try:
        event_row = {
            "event_id": str(uuid.uuid4()),
            "event_type": "FORMAT_ROUTED",
            "timestamp": datetime.utcnow().isoformat(),
            "actor_type": "SYSTEM",
            "actor_id": "pipeline_format_router",
            "actor_role": "SYSTEM",
            "target_type": "DOCUMENT",
            "target_id": document_id,
            "payload": json.dumps({
                "detected_format": detected_format,
                "routing_pipeline": routing_pipeline,
            }),
            "metadata": None,
            "idempotency_key": f"fmt_{document_id}",
        }
        
        table = "autohaus-infrastructure.autohaus_cil.cil_events"
        errors = bq_client.insert_rows_json(table, [event_row])
        if errors:
            logger.error(f"[FORMAT] Failed to emit FORMAT_ROUTED event: {errors}")
    except Exception as e:
        logger.error(f"[FORMAT] Event emission failed: {e}")
