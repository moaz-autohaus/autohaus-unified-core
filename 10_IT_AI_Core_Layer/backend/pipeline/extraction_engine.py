"""
AutoHaus CIL — Extraction Engine
Phase 2, Step 6

Uses Gemini Flash for document classification and field extraction.
Falls back to Gemini Pro 3.1 only for KAMM compliance docs or low-confidence results.

The 90/10 Hybrid Pipeline:
  1. Deterministic first (regex, exact match) — free
  2. Gemini Flash for standard extraction — cheap
  3. Gemini Pro 3.1 only for compliance/ambiguity — expensive, reserved
"""

import os
import re
import uuid
import json
import yaml
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("autohaus.extraction_engine")

from database.policy_engine import get_policy

# Load all YAML schemas at module init
SCHEMAS_DIR = Path(__file__).parent / "schemas"
_schema_cache: Dict[str, dict] = {}


def _load_schemas():
    """Load all YAML schemas from disk into memory."""
    global _schema_cache
    if _schema_cache:
        return
    for yaml_file in SCHEMAS_DIR.glob("*.yaml"):
        try:
            with open(yaml_file) as f:
                schema = yaml.safe_load(f)
            schema_id = schema.get("schema_id")
            if schema_id:
                _schema_cache[schema_id] = schema
                logger.info(f"[SCHEMA] Loaded: {schema_id} v{schema.get('schema_version', '?')}")
        except Exception as e:
            logger.error(f"[SCHEMA] Failed to load {yaml_file}: {e}")


def get_schema(schema_id: str) -> Optional[dict]:
    """Get a loaded schema by ID."""
    _load_schemas()
    return _schema_cache.get(schema_id)


def list_schemas() -> List[str]:
    """List all available schema IDs."""
    _load_schemas()
    return list(_schema_cache.keys())


def _build_classification_prompt(text_content: str) -> str:
    """Build the Gemini prompt for document classification."""
    _load_schemas()
    schema_list = "\n".join(
        f"- {sid}: {s.get('description', '')}" for sid, s in _schema_cache.items()
    )
    return f"""You are a document classification engine for an auto dealership called AutoHaus.

Given the text content of a document, classify it into exactly ONE of these document types:
{schema_list}
- UNKNOWN: Does not match any known type

Respond with ONLY a JSON object in this exact format:
{{"doc_type": "SCHEMA_ID_HERE", "confidence": 0.95, "reasoning": "brief explanation"}}

Do not include any other text. Just the JSON.

Document text:
---
{text_content[:3000]}
---"""


def _build_extraction_prompt(text_content: str, schema: dict) -> str:
    """Build the Gemini prompt for structured field extraction."""
    schema_id = schema["schema_id"]
    
    # Build field list for the prompt
    required = schema.get("required_fields", [])
    optional = schema.get("optional_fields", [])
    
    field_instructions = "REQUIRED FIELDS (must extract or mark null):\n"
    for f in required:
        extra = ""
        if f.get("pattern"):
            extra += f" [pattern: {f['pattern']}]"
        if f.get("enum"):
            extra += f" [one of: {', '.join(f['enum'])}]"
        field_instructions += f"  - {f['name']} ({f['type']}){extra}\n"
    
    field_instructions += "\nOPTIONAL FIELDS (extract if present):\n"
    for f in optional:
        extra = ""
        if f.get("enum"):
            extra += f" [one of: {', '.join(f['enum'])}]"
        field_instructions += f"  - {f['name']} ({f['type']}){extra}\n"
    
    return f"""You are a precise document data extraction engine for AutoHaus, an auto dealership.

This document has been classified as: {schema_id} — {schema.get('description', '')}

Extract ALL fields listed below from the document text. For each field, provide the extracted value and your confidence (0.0 to 1.0).

{field_instructions}

Respond with ONLY a JSON object in this exact format:
{{
  "fields": {{
    "field_name": {{"value": "extracted_value", "confidence": 0.95}},
    ...
  }},
  "extraction_notes": "any issues or ambiguities noticed"
}}

Rules:
- If a required field is not found, set value to null and confidence to 0.0
- For dates, use ISO format: YYYY-MM-DD
- For decimals/money, use numeric values without currency symbols: 1500.00
- For VINs, uppercase only, exactly 17 characters
- Do not guess. If unsure, lower the confidence.

Document text:
---
{text_content[:5000]}
---"""


def _call_gemini(prompt: str, use_pro: bool = False) -> Optional[dict]:
    """
    Call Gemini API and parse JSON response.
    Uses Flash by default. Switches to Pro only when use_pro=True.
    """
    try:
        import google.generativeai as genai
        
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("[GEMINI] No GEMINI_API_KEY found in environment.")
            return None
        
        genai.configure(api_key=api_key)
        
        model_name = "gemini-flash-latest" if not use_pro else "gemini-pro-latest"
        model = genai.GenerativeModel(model_name)
        
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"[GEMINI] Failed to parse JSON response: {e}")
        logger.debug(f"[GEMINI] Raw response: {text[:500] if 'text' in dir() else 'N/A'}")
        return None
    except Exception as e:
        logger.error(f"[GEMINI] API call failed: {e}")
        return None


def classify_document(text_content: str) -> Tuple[str, float]:
    """
    Classify a document's text content into a schema type.
    Returns (doc_type, confidence).
    """
    prompt = _build_classification_prompt(text_content)
    result = _call_gemini(prompt, use_pro=False)  # Flash is fine for classification
    
    if not result:
        return "UNKNOWN", 0.0
    
    doc_type = result.get("doc_type", "UNKNOWN")
    confidence = float(result.get("confidence", 0.0))
    
    # Validate the returned doc_type exists in our schemas
    _load_schemas()
    if doc_type != "UNKNOWN" and doc_type not in _schema_cache:
        logger.warning(f"[CLASSIFY] Gemini returned unknown schema_id: {doc_type}")
        return "UNKNOWN", 0.0
    
    return doc_type, confidence


def extract_fields(
    text_content: str,
    doc_type: str,
    document_id: str,
    bq_client=None,
) -> Optional[Dict[str, Any]]:
    """
    Extract structured fields from document text using the appropriate schema.
    
    Returns dict of extracted fields with confidence scores, or None on failure.
    """
    schema = get_schema(doc_type)
    if not schema:
        logger.error(f"[EXTRACT] No schema found for doc_type: {doc_type}")
        return None
    
    # Decide: Flash or Pro? based on Policy Registry
    use_pro = str(get_policy("COMPLIANCE", "kamm_review_required", doc_type=doc_type) or "").lower() == "true"
    if use_pro:
        logger.info(f"[EXTRACT] KAMM document ({doc_type}) — using Gemini Pro 3.1")
    
    prompt = _build_extraction_prompt(text_content, schema)
    result = _call_gemini(prompt, use_pro=use_pro)
    
    if not result or "fields" not in result:
        logger.error(f"[EXTRACT] Extraction returned no fields for {document_id}")
        return None
    
    extracted = result["fields"]
    extraction_version_id = str(uuid.uuid4())
    threshold = float(get_policy("EXTRACTION", "min_confidence_threshold", doc_type=doc_type) or schema.get("confidence_threshold", 0.85))
    
    # Post-processing: validate patterns, check thresholds
    processed_fields = {}
    needs_review = False
    
    for field_name, field_data in extracted.items():
        value = field_data.get("value")
        confidence = float(field_data.get("confidence", 0.0))
        
        # Find field definition in schema
        field_def = None
        for f in schema.get("required_fields", []) + schema.get("optional_fields", []):
            if f["name"] == field_name:
                field_def = f
                break
        
        # Pattern validation (e.g., VIN format)
        pattern_valid = True
        if field_def and field_def.get("pattern") and value:
            if not re.match(field_def["pattern"], str(value)):
                pattern_valid = False
                confidence = min(confidence, 0.3)  # Penalize bad pattern match
                logger.warning(f"[EXTRACT] {field_name} failed pattern check: {value}")
        
        # Enum validation
        if field_def and field_def.get("enum") and value:
            if str(value).upper() not in [e.upper() for e in field_def["enum"]]:
                confidence = min(confidence, 0.5)
                logger.warning(f"[EXTRACT] {field_name} not in enum: {value}")
        
        # Flag for review if below threshold
        field_needs_review = confidence < threshold
        if field_needs_review:
            needs_review = True
        
        processed_fields[field_name] = {
            "value": value,
            "confidence": confidence,
            "pattern_valid": pattern_valid,
            "requires_review": field_needs_review,
            "field_type": field_def.get("type", "string") if field_def else "string",
        }
    
    # KAMM override: always require review regardless of confidence
    is_kamm = str(get_policy("COMPLIANCE", "kamm_review_required", doc_type=doc_type) or "false").lower() == "true"
    if is_kamm:
        needs_review = True
    
    # Write to BigQuery extraction_fields table
    if bq_client:
        _write_extraction_fields(
            bq_client, document_id, extraction_version_id,
            doc_type, schema.get("schema_version", "1.0"),
            processed_fields, needs_review
        )
    
    return {
        "extraction_version_id": extraction_version_id,
        "doc_type": doc_type,
        "fields": processed_fields,
        "needs_review": needs_review,
        "notes": result.get("extraction_notes", ""),
    }


def _write_extraction_fields(
    bq_client, document_id: str, extraction_version_id: str,
    schema_id: str, schema_version: str,
    fields: Dict[str, Any], needs_review: bool
):
    """Write extracted fields to BigQuery."""
    rows = []
    now = datetime.utcnow().isoformat()
    
    for field_name, field_data in fields.items():
        rows.append({
            "field_id": str(uuid.uuid4()),
            "document_id": document_id,
            "extraction_version_id": extraction_version_id,
            "schema_id": schema_id,
            "field_name": field_name,
            "field_value": str(field_data["value"]) if field_data["value"] is not None else None,
            "field_type": field_data.get("field_type", "string"),
            "extraction_confidence": field_data["confidence"],
            "authority_level": "ADVISORY",
            "source_location": None,
            "requires_review": field_data.get("requires_review", False),
            "active_override_id": None,
            "effective_value": str(field_data["value"]) if field_data["value"] is not None else None,
            "created_at": now,
        })
    
    if rows:
        table = "autohaus-infrastructure.autohaus_cil.extraction_fields"
        errors = bq_client.insert_rows_json(table, rows)
        if errors:
            logger.error(f"[EXTRACT] Failed to write extraction_fields: {errors}")
        else:
            logger.info(f"[EXTRACT] Wrote {len(rows)} fields for {document_id}")
    
    # Emit FIELD_EXTRACTED event
    try:
        event_row = {
            "event_id": str(uuid.uuid4()),
            "event_type": "FIELD_EXTRACTED",
            "timestamp": now,
            "actor_type": "SYSTEM",
            "actor_id": "extraction_engine",
            "actor_role": "SYSTEM",
            "target_type": "DOCUMENT",
            "target_id": document_id,
            "payload": json.dumps({
                "schema": schema_id,
                "fields": {k: {"value": v["value"], "confidence": v["confidence"]} for k, v in fields.items()},
            }),
            "metadata": None,
            "idempotency_key": f"extract_{document_id}_{extraction_version_id}",
        }
        events_table = "autohaus-infrastructure.autohaus_cil.cil_events"
        bq_client.insert_rows_json(events_table, [event_row])
    except Exception as e:
        logger.error(f"[EXTRACT] Failed to emit FIELD_EXTRACTED event: {e}")
