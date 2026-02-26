"""
AutoHaus CIL — Entity Resolution Engine
Phase 2, Step 7

Connects extracted document fields to master entity tables.
VIN is the anchor: resolve vehicles first, then attach everything else
through the vehicle relationship.

Resolution Strategy (from Blueprint):
  VEHICLE:  VIN exact match — deterministic, no fuzzy
  PERSON:   Phone + email primary, name fallback
  VENDOR:   Normalize → strip suffixes → uppercase → alias table
  COMPANY:  Exact match vs business_ontology.json active_entities
"""

import os
import re
import uuid
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from database.relationship_validator import is_valid_edge
from database.open_questions import raise_open_question
from .truth_projection import project_entity_fact, rebuild_entity_facts

logger = logging.getLogger("autohaus.entity_resolution")

def _run_enrichment_background(bq_client, entity_type: str, entity_id: str, trigger: str, primary_key: str):
    """Fires the Enrichment Engine asynchronously in a background thread so it doesn't block."""
    def _worker():
        try:
            import asyncio
            from enrichment.enrichment_engine import EnrichmentEngine
            engine = EnrichmentEngine(bq_client)
            asyncio.run(engine.enrich(
                entity_type=entity_type,
                entity_id=entity_id,
                trigger=trigger,
                primary_key=primary_key
            ))
        except Exception as e:
            logger.error(f"[ENRICH] Background worker failed: {e}")
            
    import threading
    t = threading.Thread(target=_worker)
    t.start()


# Internal companies — exact match only
INTERNAL_COMPANIES = {
    "KAMM_LLC", "KAMM LLC", "KAMM",
    "AUTOHAUS_SERVICES_LLC", "AUTOHAUS SERVICES LLC", "AUTOHAUS SERVICES",
    "CARLUX_LLC", "CARLUX LLC", "CARLUX",
    "FLUIDITRUCK_LLC", "FLUIDITRUCK LLC", "FLUIDITRUCK",
    "ASTROLOGISTICS_LLC", "ASTROLOGISTICS LLC", "ASTROLOGISTICS",
}

# Suffixes to strip during vendor normalization
VENDOR_SUFFIXES = [
    r"\s+INC\.?$", r"\s+LLC\.?$", r"\s+CORP\.?$", r"\s+CO\.?$",
    r"\s+LTD\.?$", r"\s+LIMITED$", r"\s+COMPANY$", r"\s+CORPORATION$",
    r"\s+INCORPORATED$", r"\s+AUTO\s+AUCTIONS?$",
]


# ── Central Entity Registry (Pass 7) ────────────────────────────────────

def _register_entity(bq_client, entity_id: str, entity_type: str, anchors: dict, authority_level: str):
    """
    Register an entity in the central entity_registry with 
    a corresponding ENTITY_CREATED CIL event.
    """
    now = datetime.utcnow().isoformat()
    status = "STUB" if authority_level == "STUB" else "ACTIVE"
    stub_reason = "Created from non-authoritative document" if status == "STUB" else None
    
    registry_row = {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "status": status,
        "stub_reason": stub_reason,
        "anchors": json.dumps(anchors),
        "aliases": json.dumps([]),
        "authority_level": authority_level,
        "completeness_score": 0.1,  # Base score
        "lineage": json.dumps([]),
        "created_at": now,
        "updated_at": now,
    }
    errors = bq_client.insert_rows_json(
        "autohaus-infrastructure.autohaus_cil.entity_registry", [registry_row]
    )
    if errors:
        logger.error(f"[REGISTRY] Failed to register {entity_type} {entity_id}: {errors}")
        
    # Emit ENTITY_CREATED event
    event_row = {
        "event_id": str(uuid.uuid4()),
        "event_type": "ENTITY_CREATED",
        "timestamp": now,
        "actor_type": "SYSTEM",
        "actor_id": "entity_resolution_engine",
        "actor_role": "SYSTEM",
        "target_type": "ENTITY",
        "target_id": entity_id,
        "payload": json.dumps({
            "entity_type": entity_type,
            "entity_id": entity_id,
            "status": status,
            "authority_level": authority_level,
            "anchors": anchors,
        }),
        "metadata": None,
        "idempotency_key": f"create_{entity_id}",
    }
    bq_client.insert_rows_json(
        "autohaus-infrastructure.autohaus_cil.cil_events", [event_row]
    )

def _promote_entity(bq_client, entity_id: str, new_level: str):
    """
    Updates the registry status to ACTIVE and updates authority level.
    """
    now = datetime.utcnow().isoformat()
    query = """
        UPDATE `autohaus-infrastructure.autohaus_cil.entity_registry`
        SET status = 'ACTIVE', authority_level = @new_level, updated_at = @now
        WHERE entity_id = @entity_id
    """
    from google.cloud import bigquery as bq
    params = [
        bq.ScalarQueryParameter("new_level", "STRING", new_level),
        bq.ScalarQueryParameter("now", "STRING", now),
        bq.ScalarQueryParameter("entity_id", "STRING", entity_id),
    ]
    try:
        bq_client.query(query, job_config=bq.QueryJobConfig(query_parameters=params)).result()
        rebuild_entity_facts(bq_client, entity_id)
    except Exception as e:
        logger.error(f"[REGISTRY] Failed to promote {entity_id} to {new_level}: {e}")

# ── Vehicle Resolution (Anchor Entity) ──────────────────────────────────

def resolve_vehicle(bq_client, vin: str) -> Tuple[str, str, Dict[str, Any]]:
    """
    Resolve a VIN to an existing vehicle entity, or create a new one.
    Returns (vehicle_id, resolution_method, current_data).
    
    VINs are EXACT MATCH ONLY — no fuzzy, no similarity, no guessing.
    new vehicles start as "STUB".
    """
    if not vin or len(vin) != 17:
        logger.warning(f"[ENTITY] Invalid VIN format: {vin}")
        return "", "INVALID_VIN", {}

    vin = vin.upper().strip()

    # Check for existing vehicle
    query = """
        SELECT vehicle_id, vin, year, make, model, trim, color, authority_level 
        FROM `autohaus-infrastructure.autohaus_cil.vehicles`
        WHERE vin = @vin LIMIT 1
    """
    from google.cloud import bigquery as bq
    job_config = bq.QueryJobConfig(
        query_parameters=[bq.ScalarQueryParameter("vin", "STRING", vin)]
    )
    
    try:
        results = list(bq_client.query(query, job_config=job_config).result())
        if results:
            return results[0].vehicle_id, "EXACT_MATCH", dict(results[0])
    except Exception as e:
        logger.error(f"[ENTITY] Vehicle lookup failed: {e}")

    # Create new vehicle entity
    vehicle_id = str(uuid.uuid4())
    row = {
        "vehicle_id": vehicle_id,
        "vin": vin,
        "year": None,
        "make": None,
        "model": None,
        "trim": None,
        "color": None,
        "authority_level": "STUB", # Start as STUB
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    # Register in central registry first
    _register_entity(bq_client, vehicle_id, "VEHICLE", {"vin": vin}, "STUB")
    
    errors = bq_client.insert_rows_json(
        "autohaus-infrastructure.autohaus_cil.vehicles", [row]
    )
    if errors:
        logger.error(f"[ENTITY] Failed to project vehicle to master table (still exists in registry): {errors}")
    
    logger.info(f"[ENTITY] Created new STUB vehicle entity: {vehicle_id} (VIN: {vin})")
    
    # Phase 8 Enrichment Pipeline
    _run_enrichment_background(bq_client, "VEHICLE", vehicle_id, "ENTITY_RESOLUTION_NEW_VIN", vin)
    
    return vehicle_id, "AUTO_CREATED", row


# ── Vendor Resolution ───────────────────────────────────────────────────

def _normalize_vendor_name(raw_name: str) -> str:
    """
    Normalize vendor name:
    1. Uppercase
    2. Strip legal suffixes (Inc, LLC, Corp, etc.)
    3. Collapse whitespace
    """
    name = raw_name.upper().strip()
    for pattern in VENDOR_SUFFIXES:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def resolve_vendor(bq_client, raw_name: str) -> Tuple[str, str]:
    """
    Resolve a vendor name to an existing vendor entity.
    Strategy: Normalize → check alias table → check canonical → create if new.
    Returns (vendor_id, resolution_method).
    """
    if not raw_name or not raw_name.strip():
        return "", "EMPTY_NAME"

    normalized = _normalize_vendor_name(raw_name)

    # Step 1: Check alias table
    from google.cloud import bigquery as bq
    alias_query = """
        SELECT canonical_vendor_id FROM `autohaus-infrastructure.autohaus_cil.vendor_aliases`
        WHERE UPPER(raw_name) = @raw_upper OR UPPER(canonical_name) = @norm
        LIMIT 1
    """
    job_config = bq.QueryJobConfig(
        query_parameters=[
            bq.ScalarQueryParameter("raw_upper", "STRING", raw_name.upper().strip()),
            bq.ScalarQueryParameter("norm", "STRING", normalized),
        ]
    )
    try:
        results = list(bq_client.query(alias_query, job_config=job_config).result())
        if results:
            return results[0].canonical_vendor_id, "VENDOR_ALIAS"
    except Exception as e:
        logger.error(f"[ENTITY] Vendor alias lookup failed: {e}")

    # Step 2: Check vendors table directly
    vendor_query = """
        SELECT vendor_id FROM `autohaus-infrastructure.autohaus_cil.vendors`
        WHERE UPPER(canonical_name) = @norm LIMIT 1
    """
    job_config = bq.QueryJobConfig(
        query_parameters=[bq.ScalarQueryParameter("norm", "STRING", normalized)]
    )
    try:
        results = list(bq_client.query(vendor_query, job_config=job_config).result())
        if results:
            # Found vendor but no alias — create alias for future lookups
            _create_vendor_alias(bq_client, raw_name, results[0].vendor_id, normalized)
            return results[0].vendor_id, "EXACT_MATCH"
    except Exception as e:
        logger.error(f"[ENTITY] Vendor lookup failed: {e}")

    # Step 3: Create new vendor + alias
    vendor_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    vendor_row = {
        "vendor_id": vendor_id,
        "canonical_name": normalized,
        "created_at": now,
        "updated_at": now,
    }
    # Register in BQ registry
    _register_entity(bq_client, vendor_id, "VENDOR", {"canonical_name": normalized}, "STUB")

    errors = bq_client.insert_rows_json(
        "autohaus-infrastructure.autohaus_cil.vendors", [vendor_row]
    )
    if errors:
        logger.error(f"[ENTITY] Failed to project vendor to master table (still exists in registry): {errors}")

    _create_vendor_alias(bq_client, raw_name, vendor_id, normalized)
    logger.info(f"[ENTITY] Created new vendor: {vendor_id} ({normalized})")

    _run_enrichment_background(bq_client, "VENDOR", vendor_id, "ENTITY_RESOLUTION_NEW_VENDOR", normalized)

    return vendor_id, "AUTO_CREATED"


def _create_vendor_alias(bq_client, raw_name: str, vendor_id: str, canonical: str):
    """Insert an alias mapping for faster future lookups."""
    row = {
        "alias_id": str(uuid.uuid4()),
        "raw_name": raw_name.strip(),
        "canonical_vendor_id": vendor_id,
        "canonical_name": canonical,
        "created_at": datetime.utcnow().isoformat(),
        "created_by": "SYSTEM",
    }
    errors = bq_client.insert_rows_json(
        "autohaus-infrastructure.autohaus_cil.vendor_aliases", [row]
    )
    if errors:
        logger.error(f"[ENTITY] Failed to create vendor alias: {errors}")


# ── Person Resolution ───────────────────────────────────────────────────

def resolve_person(bq_client, name: str, phone: Optional[str] = None, email: Optional[str] = None) -> Tuple[str, str, Dict[str, Any]]:
    """
    Resolve a person by phone+email (primary) or name (fallback).
    Returns (person_id, resolution_method, current_data).
    """
    if not name and not phone and not email:
        return "", "EMPTY_IDENTITY", {}

    from google.cloud import bigquery as bq

    # Step 1: Try phone + email match (strongest signal)
    if phone or email:
        conditions = []
        params = []
        if phone:
            clean_phone = re.sub(r"[^\d]", "", phone)
            if len(clean_phone) >= 10:
                conditions.append("REGEXP_REPLACE(phone, r'[^0-9]', '') = @phone")
                params.append(bq.ScalarQueryParameter("phone", "STRING", clean_phone))
        if email:
            conditions.append("LOWER(email) = @email")
            params.append(bq.ScalarQueryParameter("email", "STRING", email.lower().strip()))

        if conditions:
            query = f"""
                SELECT person_id, canonical_name, phone, email, authority_level 
                FROM `autohaus-infrastructure.autohaus_cil.persons`
                WHERE {" OR ".join(conditions)} LIMIT 1
            """
            job_config = bq.QueryJobConfig(query_parameters=params)
            try:
                results = list(bq_client.query(query, job_config=job_config).result())
                if results:
                    return results[0].person_id, "IDENTITY_ENGINE", dict(results[0])
            except Exception as e:
                logger.error(f"[ENTITY] Person identity lookup failed: {e}")

    # Step 2: Name-based fallback (weaker — may create duplicates, fixable via HITL)
    if name:
        name_clean = name.upper().strip()
        query = """
            SELECT person_id, canonical_name, phone, email, authority_level 
            FROM `autohaus-infrastructure.autohaus_cil.persons`
            WHERE UPPER(canonical_name) = @name LIMIT 1
        """
        job_config = bq.QueryJobConfig(
            query_parameters=[bq.ScalarQueryParameter("name", "STRING", name_clean)]
        )
        try:
            results = list(bq_client.query(query, job_config=job_config).result())
            if results:
                return results[0].person_id, "NAME_MATCH", dict(results[0])
        except Exception as e:
            logger.error(f"[ENTITY] Person name lookup failed: {e}")

    # Step 3: Create new person
    person_id = str(uuid.uuid4())
    row = {
        "person_id": person_id,
        "canonical_name": name.strip() if name else None,
        "phone": phone.strip() if phone else None,
        "email": email.strip().lower() if email else None,
        "authority_level": "STUB",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    # Register in central registry
    anchors = {}
    if phone: anchors["phone"] = phone.strip()
    if email: anchors["email"] = email.strip().lower()
    if name: anchors["canonical_name"] = name.strip()
    _register_entity(bq_client, person_id, "PERSON", anchors, "STUB")

    errors = bq_client.insert_rows_json(
        "autohaus-infrastructure.autohaus_cil.persons", [row]
    )
    if errors:
        logger.error(f"[ENTITY] Failed to project person to master table (still exists in registry): {errors}")
    
    logger.info(f"[ENTITY] Created new STUB person: {person_id} ({name})")

    _run_enrichment_background(bq_client, "PERSON", person_id, "ENTITY_RESOLUTION_NEW_PERSON", email or phone or name)

    return person_id, "AUTO_CREATED", row


# ── Company Resolution (Internal Only) ─────────────────────────────────

def resolve_company(raw_name: str) -> Tuple[str, str]:
    """
    Resolve an internal company entity. This is a deterministic lookup
    against the known set of AutoHaus entities. No BigQuery needed.
    Returns (canonical_name, resolution_method).
    """
    if not raw_name:
        return "", "EMPTY_NAME"
    
    name_upper = raw_name.upper().strip()
    name_upper = re.sub(r"[_\s]+", " ", name_upper)
    
    for company in INTERNAL_COMPANIES:
        if company.replace("_", " ") in name_upper or name_upper in company.replace("_", " "):
            canonical = company.replace(" ", "_")
            if not canonical.endswith("_LLC") and canonical + "_LLC" in INTERNAL_COMPANIES:
                canonical = canonical + "_LLC"
            return canonical, "EXACT_MATCH"
    
    return raw_name, "UNRESOLVED"


# ── Master Linker ───────────────────────────────────────────────────────

def link_document_entities(
    bq_client,
    document_id: str,
    extracted_fields: Dict[str, Any],
    schema: dict,
) -> List[dict]:
    """
    Given extracted fields and a schema's entity_links, resolve all entities
    and create document_entity_links records.
    
    Returns list of created links for downstream use.
    """
    entity_links_def = schema.get("entity_links", [])
    if not entity_links_def:
        return []

    created_links = []
    now = datetime.utcnow().isoformat()
    
    for link_def in entity_links_def:
        field_name = link_def.get("field")
        entity_type = link_def.get("entity_type", "").upper()
        
        # Get the extracted value for this field
        field_data = extracted_fields.get(field_name, {})
        value = field_data.get("value") if isinstance(field_data, dict) else field_data
        
        if not value:
            continue

        # Resolve entity based on type
        entity_id = None
        resolution_method = None
        current_data = {}
        confidence = 0.0

        if entity_type == "VEHICLE":
            entity_id, resolution_method, current_data = resolve_vehicle(bq_client, str(value))
            confidence = 1.0 if resolution_method in ("EXACT_MATCH", "AUTO_CREATED") else 0.0
            
            # Enrich Vehicle if needed
            if entity_id and resolution_method == "EXACT_MATCH":
                _enrich_vehicle_metadata(bq_client, entity_id, current_data, extracted_fields, schema, document_id)

        elif entity_type == "VENDOR":
            entity_id, resolution_method = resolve_vendor(bq_client, str(value))
            confidence = 1.0 if resolution_method != "CREATE_FAILED" else 0.0

        elif entity_type in ("PERSON", "PERSON | COMPANY"):
            # Try person first
            entity_id, resolution_method, current_data = resolve_person(bq_client, str(value))
            entity_type = "PERSON"
            confidence = 0.9 if resolution_method == "IDENTITY_ENGINE" else 0.7
            
            # Enrich Person if needed
            if entity_id and resolution_method in ("IDENTITY_ENGINE", "NAME_MATCH"):
                _enrich_person_metadata(bq_client, entity_id, current_data, extracted_fields, schema, document_id)

        if not entity_id:
            logger.warning(f"[LINK] Could not resolve {field_name}={value} as {entity_type}")
            continue

        # Determine relationship type from context
        relationship = _infer_relationship(field_name, entity_type)

        if not is_valid_edge("DOCUMENT", entity_type, relationship):
             logger.warning(f"[LINK] Blocked invalid edge DOCUMENT -> {entity_type} [{relationship}]")
             raise_open_question(
                 bq_client, 
                 question_type="INVALID_EDGE",
                 priority="MEDIUM",
                 context={
                     "document_id": document_id, "entity_id": entity_id, 
                     "target_type": entity_type, "relationship_type": relationship
                 },
                 description=f"System blocked invalid relationship {relationship} between DOCUMENT and {entity_type}"
             )
             continue

        # Create the link
        link_id = str(uuid.uuid4())
        link_row = {
            "link_id": link_id,
            "document_id": document_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "relationship_type": relationship,
            "resolution_method": resolution_method,
            "resolution_confidence": confidence,
            "active": True,
            "superseded_by_link_id": None,
            "created_at": now,
            "created_by_event_id": None,  # Will be set by the cil_event below
        }

        errors = bq_client.insert_rows_json(
            "autohaus-infrastructure.autohaus_cil.document_entity_links", [link_row]
        )
        if errors:
            logger.error(f"[LINK] Failed to create link: {errors}")
        else:
            created_links.append(link_row)

        # Emit ENTITY_LINKED event
        event_row = {
            "event_id": str(uuid.uuid4()),
            "event_type": "ENTITY_LINKED",
            "timestamp": now,
            "actor_type": "SYSTEM",
            "actor_id": "entity_resolution_engine",
            "actor_role": "SYSTEM",
            "target_type": "DOCUMENT",
            "target_id": document_id,
            "payload": json.dumps({
                "entity_type": entity_type,
                "entity_id": entity_id,
                "confidence": confidence,
                "method": resolution_method,
            }),
            "metadata": None,
            "idempotency_key": f"link_{document_id}_{entity_type}_{entity_id}",
        }
        bq_client.insert_rows_json(
            "autohaus-infrastructure.autohaus_cil.cil_events", [event_row]
        )

    logger.info(f"[LINK] Created {len(created_links)} entity links for document {document_id}")
    return created_links


def _infer_relationship(field_name: str, entity_type: str) -> str:
    """Infer the relationship type from the field name and entity type."""
    mapping = {
        "vin": "SUBJECT",
        "owner_name": "OWNER",
        "buyer_name": "COUNTERPARTY",
        "seller_name": "COUNTERPARTY",
        "auction_house": "SOURCE",
        "carrier_name": "SOURCE",
        "lender_name": "SOURCE",
        "insured_entity": "INSURED",
        "lien_holder": "REFERENCE",
        "service_entity": "SOURCE",
        "technician_name": "REFERENCE",
        "dispatch_entity": "SOURCE",
    }
    return mapping.get(field_name, "REFERENCE")


# ── Enrichment Logic ───────────────────────────────────────────────────

def _enrich_vehicle_metadata(bq_client, vehicle_id: str, current: dict, extracted: dict, schema: dict, document_id: str):
    """
    Updates vehicle fields if new data is more authoritative or fills gaps.
    Sovereign docs (TITLES) promote STUB -> SOVEREIGN.
    """
    schema_id = schema.get("schema_id", "UNKNOWN")
    is_sovereign = schema_id in ("VEHICLE_TITLE", "TITLE_REASSIGNMENT", "BILL_OF_SALE")
    
    updates = {}
    enriched_fields = []
    
    # Map extracted values to table columns
    # Note: extracted fields might be raw dicts {"value": ..., "confidence": ...}
    def get_val(f):
        val = extracted.get(f)
        return val.get("value") if isinstance(val, dict) else val

    # Fill missing fields & Project Facts
    for field in ["year", "make", "model", "trim", "color"]:
        field_data = extracted.get(field, {})
        new_val = field_data.get("value") if isinstance(field_data, dict) else field_data
        conf = float(field_data.get("confidence", 0.85)) if isinstance(field_data, dict) else 0.85
        
        if new_val:
            project_entity_fact(bq_client, vehicle_id, "VEHICLE", field, str(new_val), conf, document_id, schema_id)
            
            if not current.get(field):
                updates[field] = new_val
                enriched_fields.append(field)
            
    # Promotion logic
    old_level = current.get("authority_level", "STUB")
    new_level = old_level
    
    if is_sovereign:
        new_level = "SOVEREIGN"
    elif old_level == "STUB":
        new_level = "ADVISORY"
        
    if new_level != old_level:
        updates["authority_level"] = new_level
        enriched_fields.append("authority_level")
        _promote_entity(bq_client, vehicle_id, new_level)

    if not updates:
        return

    # Apply via BigQuery DML
    updates["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join([f"{k} = @{k}" for k in updates.keys()])
    
    from google.cloud import bigquery as bq
    params = [bq.ScalarQueryParameter(k, "STRING" if k != "year" else "INT64", v) for k, v in updates.items()]
    params.append(bq.ScalarQueryParameter("vid", "STRING", vehicle_id))
    
    query = f"UPDATE `autohaus-infrastructure.autohaus_cil.vehicles` SET {set_clause} WHERE vehicle_id = @vid"
    
    try:
        bq_client.query(query, job_config=bq.QueryJobConfig(query_parameters=params)).result()
        logger.info(f"[ENRICH] Vehicle {vehicle_id} enriched: {', '.join(enriched_fields)}")
        
        # Emit event
        _emit_enrichment_event(bq_client, "VEHICLE", vehicle_id, enriched_fields, schema_id)
        
        # Rebuild facts (New Extraction trigger)
        rebuild_entity_facts(bq_client, vehicle_id)
    except Exception as e:
        logger.error(f"[ENRICH] Failed to update vehicle {vehicle_id}: {e}")


def _enrich_person_metadata(bq_client, person_id: str, current: dict, extracted: dict, schema: dict, document_id: str):
    """Fills missing phone/email on persons."""
    updates = {}
    enriched_fields = []
    schema_id = schema.get("schema_id", "UNKNOWN")
    
    def get_val(f):
        val = extracted.get(f)
        return val.get("value") if isinstance(val, dict) else val
        
    for field in ["phone", "email"]:
        field_data = extracted.get(field, {})
        new_val = field_data.get("value") if isinstance(field_data, dict) else field_data
        conf = float(field_data.get("confidence", 0.85)) if isinstance(field_data, dict) else 0.85

        if new_val:
            project_entity_fact(bq_client, person_id, "PERSON", field, str(new_val), conf, document_id, schema_id)

            if not current.get(field):
                updates[field] = new_val
                enriched_fields.append(field)
            
    if not updates:
        return
        
    updates["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join([f"{k} = @{k}" for k in updates.keys()])
    
    from google.cloud import bigquery as bq
    params = [bq.ScalarQueryParameter(k, "STRING", v) for k, v in updates.items()]
    params.append(bq.ScalarQueryParameter("pid", "STRING", person_id))
    
    query = f"UPDATE `autohaus-infrastructure.autohaus_cil.persons` SET {set_clause} WHERE person_id = @pid"
    
    try:
        bq_client.query(query, job_config=bq.QueryJobConfig(query_parameters=params)).result()
        logger.info(f"[ENRICH] Person {person_id} enriched: {', '.join(enriched_fields)}")
        _emit_enrichment_event(bq_client, "PERSON", person_id, enriched_fields, schema.get("schema_id", "UNKNOWN"))
        
        # Rebuild facts (New Extraction trigger)
        rebuild_entity_facts(bq_client, person_id)
    except Exception as e:
        logger.error(f"[ENRICH] Failed to update person {person_id}: {e}")


def _emit_enrichment_event(bq_client, entity_type: str, entity_id: str, fields: List[str], source: str):
    """Logs the enrichment to cil_events."""
    event_row = {
        "event_id": str(uuid.uuid4()),
        "event_type": "ENTITY_ENRICHED",
        "timestamp": datetime.utcnow().isoformat(),
        "actor_type": "SYSTEM",
        "actor_id": "entity_resolution_engine",
        "actor_role": "SYSTEM",
        "target_type": entity_type,
        "target_id": entity_id,
        "payload": json.dumps({
            "enriched_fields": fields,
            "source_document_type": source
        }),
        "metadata": None,
        "idempotency_key": f"enrich_{entity_id}_{datetime.utcnow().strftime('%Y%m%d%H%M')}"
    }
    bq_client.insert_rows_json("autohaus-infrastructure.autohaus_cil.cil_events", [event_row])
