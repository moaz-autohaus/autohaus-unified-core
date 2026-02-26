# AutoHaus CIL — MASTER BLUEPRINT v2.1
# Last Updated: 2026-02-25
# Status: Architecture Complete — Implementation Phase Beginning
# Audience: Any AI system or engineer resuming this project

---

## HOW TO USE THIS DOCUMENT

This is the single source of truth for AutoHaus CIL implementation.
If picked up by a new AI session: read entirely before taking any action.
Every settled decision is recorded here. Do not re-debate settled items.
Track implementation progress in Section 8 (Micro-Order Checklist).

---

## 1. SYSTEM IDENTITY & CORE PRINCIPLES

**Project:** AutoHaus Central Intelligence Layer (CIL)
**Codename:** C-OS (Conversational Operating System)
**Owner:** Ahsin (CEO, SOVEREIGN), Moaz (Logistics, FIELD)
**Infrastructure:** Replit (runtime) · BigQuery (truth) · Google Drive (archive/ingestion) · GCP (services)

**Core Principles (non-negotiable):**
1. Drive = ingestion surface + human-readable archive.
2. BigQuery = operational truth.
3. FastAPI Membrane = only writer to canonical BigQuery tables.
4. **Single Audit Spine:** `cil_events` is the immutable ledger. All master tables are derived projections.
5. **No raw DB queries:** Humans query BigQuery via the API ONLY. The API enforces role-based access control.
6. Compliance risk overrides automation convenience.
7. No corpus seeding until implementation step 8 passes.

---

## 2. CURRENT SYSTEM STATE (2026-02-25)

### IMMEDIATE FIX REQUIRED
Open Replit Secrets → delete `GCP_SERVICE_ACCOUNT_JSON` → paste raw JSON with NO surrounding single quotes → restart backend → confirm `[DRIVE_EAR] Ready` in console.

---

## 3. SETTLED ARCHITECTURAL DECISIONS

### A. Queue Architecture & Idempotency
- **Pub/Sub** receives the "file detected" trigger from Drive Ear.
- **Cloud Tasks** manages per-document processing (retries, timeouts, rate limiting).
- **Idempotency Key:** `hash(drive_file_id + file_byte_size)`. Cloud Tasks drops duplicate queue items.

### B. OCR Output Contract
- **Engine:** Google Document AI (Form Parser).
- **Storage:** Raw extracted text JSON is too large for BigQuery. It is saved to Cloud Storage: `gs://autohaus-cil-ocr-data/`.
- **Database:** BigQuery stores only the GCS URI, `page_count`, and `confidence_avg`.
- **Confidence:** Printed invoice 0.85 / vehicle title 0.80. VIN hard rule: < 0.95 forces human review.

### C. Version Grouping Rule (Strict Formulation)
To group "different physical scans of the same logical document":
1. If `content_hash` exact match → terminal_state = `DUPLICATE`.
2. Else if (same `doc_type` AND same `VIN` AND text minhash similarity > 0.85) → apply existing `version_group_id`.
3. Else → generate new `version_group_id`.

### D. Entities & Resolution
- **VIN (Anchor Context):** Exact match ONLY. 
- **Person:** Phone+email primary; fallback IdentityEngine.
- **Vendor:** Normalize → uppercase → `vendor_alias_table`.
- **Company:** Exact match vs `business_ontology.json`.

---

## 4. BIGQUERY DATA MODEL (Schemas)

All tables exist in `autohaus-infrastructure.autohaus_cil`.

### 4.1 The Single Audit Spine: `cil_events`
```sql
CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.cil_events` (
  event_id STRING NOT NULL,
  event_type STRING NOT NULL,
  timestamp TIMESTAMP NOT NULL,
  actor_type STRING NOT NULL,        -- SYSTEM | HUMAN
  actor_id STRING,
  actor_role STRING,
  target_type STRING NOT NULL,       -- DOCUMENT | ENTITY | TRANSACTION | PLATE
  target_id STRING NOT NULL,
  payload JSON,                      -- Must conform to Event Payload Registry (Sec 5)
  metadata JSON,                     -- latency_ms, api_model, cost_usd
  idempotency_key STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
) PARTITION BY DATE(timestamp) CLUSTER BY event_type, target_type;
```

### 4.2 Document Projections
```sql
CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.documents` (
  document_id STRING NOT NULL,
  content_hash STRING NOT NULL,
  filename_original STRING,
  detected_format STRING,
  drive_file_id STRING,
  archive_path STRING,
  doc_type STRING,
  classification_confidence FLOAT64,
  authority_level STRING DEFAULT 'ADVISORY',  -- ADVISORY|ASSERTED|VERIFIED|COMPLIANCE_VERIFIED|FORMALLY_IMMUTABLE|CONFLICTING_CLAIM
  version INT64 DEFAULT 1,
  version_group_id STRING,
  latest_version BOOL DEFAULT TRUE,
  amendment_lock BOOL DEFAULT FALSE,
  terminal_state STRING NOT NULL DEFAULT 'INGESTED',  -- INGESTED|PROCESSED|NEEDS_REVIEW|FAILED_UNPROCESSABLE|DUPLICATE|UNCLASSIFIED
  requires_human_review BOOL DEFAULT FALSE,
  kamm_compliance_type BOOL DEFAULT FALSE,
  ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
) PARTITION BY DATE(ingested_at) CLUSTER BY doc_type, terminal_state;

CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.document_relationships` (
  relationship_id STRING NOT NULL,
  from_document_id STRING NOT NULL,
  to_document_id STRING NOT NULL,
  relationship_type STRING NOT NULL,  -- SUPERSEDES | AMENDMENT_OF | REPLACES_SCAN_OF | RELATED_TO
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  created_by_event_id STRING NOT NULL
);
```

### 4.3 Master Entities (Minimal v0.1 Data Shapes)
These are derived projections. They only update when a `cil_events` record is written.

```sql
CREATE TABLE vehicles (vehicle_id STRING, vin STRING NOT NULL, year INT64, make STRING, model STRING, created_at TIMESTAMP);
CREATE TABLE persons (person_id STRING, canonical_name STRING, phone STRING, email STRING, created_at TIMESTAMP);
CREATE TABLE vendors (vendor_id STRING, canonical_name STRING, created_at TIMESTAMP);
CREATE TABLE transactions (transaction_id STRING, vin STRING, vendor_id STRING, amount DECIMAL, transaction_date DATE, type STRING);
CREATE TABLE jobs (job_id STRING, vin STRING, service_entity STRING, ro_number STRING, total_cost DECIMAL, closed BOOL);
```

### 4.4 HITL & Fields
```sql
-- hitl_events is the STATE MACHINE, not the ledger. 
-- When status='APPLIED', it emits a cil_events record.
CREATE TABLE `autohaus-infrastructure.autohaus_cil.hitl_events` (
  hitl_event_id STRING NOT NULL,
  action_type STRING NOT NULL,       -- CONTEXT_ADD | FIELD_OVERRIDE | ENTITY_MERGE | REPROCESS
  status STRING DEFAULT 'PROPOSED',  -- PROPOSED | VALIDATED | APPLIED | REJECTED | EXPIRED
  target_id STRING NOT NULL,
  payload JSON NOT NULL,
  diff JSON,
  proposal_expires_at TIMESTAMP,
  applied_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE `autohaus-infrastructure.autohaus_cil.extraction_fields` (
  field_id STRING NOT NULL,
  document_id STRING NOT NULL,
  schema_id STRING,
  field_name STRING NOT NULL,
  field_value STRING,
  effective_value STRING,            -- Overriden value if applicable
  extraction_confidence FLOAT64,
  authority_level STRING DEFAULT 'ADVISORY',
  active_override_id STRING
);
```

---

## 5. EVENT PAYLOAD REGISTRY

To prevent JSON drift, all `cil_events` payloads must match these shapes exactly:

- **`DOCUMENT_REGISTERED`**: `{ "drive_id": "", "content_hash": "", "mime": "" }`
- **`OCR_COMPLETED`**: `{ "page_count": 0, "confidence_avg": 0.0, "ocr_gcs_uri": "gs://..." }`
- **`FIELD_EXTRACTED`**: `{ "schema": "", "fields": { "vin": {"value": "", "confidence": 0.9} } }`
- **`HITL_FIELD_OVERRIDE_APPLIED`**: `{ "field_name": "", "old_value": "", "new_value": "", "hitl_event_id": "" }`
- **`ENTITY_LINKED`**: `{ "entity_type": "", "entity_id": "", "confidence": 0.0, "method": "EXACT_MATCH" }`

---

## 6. ROLE PERMISSIONS (API ENFORCED)

**Rule:** Nobody queries BigQuery directly. The FastAPI app uses a Service Account to query and enforces access at the API route layer.

- **AHSIN_CEO (SOVEREIGN):** `{"scope": "ALL", "permissions": ["READ", "WRITE", "OVERRIDE_COMPLIANCE", "MERGE_ENTITY", "ROLLBACK"]}`
- **ASIM/MOHSIN (STANDARD):** `{"scope": "LANE_A_AND_B", "permissions": ["READ", "WRITE_FIELDS", "REPROCESS"]}`
- **MOAZ (FIELD):** `{"scope": "FLUIDITRUCK_CARLUX", "permissions": ["READ", "ADD_CONTEXT"]}`

---

## 7. EXTRACTION SCHEMAS & COMPLIANCE

**KAMM_MUST_REVIEW** (Always `requires_human_review = TRUE`, `amendment_lock = TRUE`):
- `DAMAGE_DISCLOSURE_IA`
- `DEALER_PLATE`
- `TITLE_REASSIGNMENT`
- `ODOMETER_DISCLOSURE`

**(Full YAML definitions for the 8 core schemas are implemented in `/backend/pipeline/schemas/*.yaml`)**

---

## 8. IMPLEMENTATION MICRO-ORDER (9-STEP PLAN) — ALL STEPS CODE-COMPLETE

Implementation completed: 2026-02-25. All code lives in `10_IT_AI_Core_Layer/backend/pipeline/`.

### Phase 1: Ingestion & Validation
- [x] **Step 1: Foundational Ledger.** `models/events.py` + `database/bigquery_client.py` + `scripts/setup_bq_schema.py`
- [x] **Step 2: Document Ingestion.** `pipeline/dedup_gate.py` (SHA-256 + BigQuery duplicate check)
- [x] **Step 3: Queues & Reliability.** `pipeline/queue_worker.py` (async queue + retry + failure logging) + `routes/pipeline_routes.py`
- [x] **Step 4: Format & OCR Rules.** `pipeline/format_router.py` (MIME detection + PDF classification + HEIC conversion)

### Phase 2: Knowledge Extraction
- [x] **Step 5: Master Entities v0.1.** `scripts/setup_phase2_schema.py` — 28 tables live in BigQuery
- [x] **Step 6: Schema Engine.** `pipeline/extraction_engine.py` + 8 YAML schemas in `pipeline/schemas/`
- [x] **Step 7: Extraction & Linking.** `pipeline/entity_resolution.py` (VIN exact + vendor alias + person phone/email)

### Phase 3: Governance & Launch
- [x] **Step 8: HITL & Governance.** `pipeline/hitl_service.py` + `routes/hitl_routes.py` + `pipeline/drift_sweep.py`
- [x] **Step 9: Seeding Toolchain.** `pipeline/seeding.py` + `scripts/run_seeding.py` (CLI with dry-run + tier select + budget cap)

### NEXT: Integration & Testing
- [ ] Wire `pipeline_router` and `hitl_router` into `main.py`
- [ ] Fix Replit `requirements.txt` (add python-magic, PyMuPDF, pillow-heif, pyyaml)
- [ ] Run `--dry-run` seeding against live Drive folders
- [ ] Process first real document end-to-end
- [ ] Deploy to Replit and verify DriveEar → pipeline → BigQuery flow

---
*End of Blueprint v2.1 — Code Complete*
