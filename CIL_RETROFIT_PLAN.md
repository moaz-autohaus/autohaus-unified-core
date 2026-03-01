# AutoHaus CIL — Architecture Review and Retrofit Plan

This implementation brief maps the Governing Doctrine and Five-Phase Retrofit Strategy against the current operational state of the AutoHaus Central Intelligence Layer (CIL). It evaluates doctrinal compliance and breaks down Phase 1 and Phase 2 into actionable implementation tasks.

---

## 1. DOCTRINE COMPLIANCE AUDIT

**1. Precision information system, not automation engine.**
* **Status:** PARTIAL
* **Evidence:** The existence of `hitl_service.py` heavily biases the system toward human decision-making. However, automation exists that bypasses this, such as direct async SMS dispatches in `logistics.py` and certain probabilistic thresholds handling identity merges automatically.

**2. Event spine is truth. Tables are projections.**
* **Status:** PARTIAL
* **Evidence:** The system operates `cil_events` and logs heavily to the audit ledger. However, endpoints like `inventory.py / promote_vehicle` issue direct mutations (`UPDATE inventory_master`) first before writing the immutable ledger entry, violating the projection concept.

**3. Structure runs first: normalize → validate → hydrate → log.**
* **Status:** VIOLATED
* **Evidence:** Modules like `attachment_processor.py` and `gmail_intel.py` ingest raw, un-normalized inputs (like PDFs or raw email text) and pass them immediately to LLMs (`gemini-2.5-flash`) for extraction without an explicit pre-validation or hydration pipeline.

**4. Intelligence fires after structure, never instead of it.**
* **Status:** VIOLATED
* **Evidence:** The `iea_agent.py` (Intelligent Membrane) evaluates raw chat stream text before the data has assumed any structure. 

**5. Intelligence has two jobs: detect gaps, detect significance.**
* **Status:** PARTIAL
* **Evidence:** `iea_agent.py` successfully detects gaps (returning `INCOMPLETE`). `attention_dispatcher.py` detects significance (urgency). However, `router_agent.py` functions as a generic classifier bridging commands, pushing beyond gap/significance detection.

**6. No significance scoring on raw strings.**
* **Status:** VIOLATED
* **Evidence:** `attention_dispatcher.evaluate_event()` directly accepts raw, unhydrated event description strings and scores them 1-10 through Gemini.

**7. Every intelligent node ends in ASK or PROCEED. Criteria are policy-defined.**
* **Status:** PARTIAL
* **Evidence:** Nodes approximate ASK/PROCEED (e.g., `IEA` returning `COMPLETE/INCOMPLETE`, `HITL` returning `PROPOSE/APPLY`), but their criteria are structurally hardcoded via prompt rules (like urgency >= 7 in the attention dispatcher) rather than managed by the existing `policy_engine.py` registry.

**8. If ASK, it becomes an operational object with owner, due time, and resolution path.**
* **Status:** PARTIAL
* **Evidence:** `open_questions.py` provides the canonical schema for this. However, many ASKs do not use it—for instance, IEA requests for clarification only exist ephemerally in `csm.py` (Waiting Room) and the UI WebSocket link.

**9. All material conflicts go to HITL. Immaterial conflicts within policy-defined tolerance log and proceed. The system prepares humans to decide, it does not decide.**
* **Status:** PARTIAL
* **Evidence:** Material conflicts (like unapproved media ingestion) successfully default to HITL proposals. However, there is no formal "Claims" conflict detection layer to evaluate whether an inbound assertion contradicts an existing `entity_facts` row before overwriting.

**10. If a conclusion changes downstream behavior, it must be logged durably or it is treated as UI-only and non-authoritative.**
* **Status:** PARTIAL
* **Evidence:** The `attention_dispatcher` decides whether to route via WebSocket or SMS—a significant change in downstream system behavior—yet this decision logic is not durably lodged in the audit ledger.

**11. Structural hygiene precedes significance detection. Significance detection without hydration is invalid.**
* **Status:** VIOLATED
* **Evidence:** In `identity_routes.py`, `trigger_membrane_attention` is fired using the unhydrated prompt string of the inbound payload.

---

## 2. PHASE 1 TASK BREAKDOWN: Structural Foundation

### Task 1.1: Define Universal Claims Schema
* **Target Outcome:** A single formal claim schema that all extraction nodes output.
* **Location:** `backend/models/claims.py` (New file)
* **Complexity:** LOW
* **Description:** Build a strict Pydantic formalization for `ExtractedClaim` ensuring fields like `entity_type`, `target_field`, `extracted_value`, `confidence`, and `source_lineage` are required properties for any AI data extraction.

### Task 1.2: Standardize Async Extraction Nodes
* **Target Outcome:** All extraction aligns to the schema contract.
* **Location:** `backend/services/gmail_intel.py`, `backend/services/attachment_processor.py`
* **Complexity:** MEDIUM
* **Description:** Refactor Gemini output parsing in the email and PDF scanners to populate the new `ExtractedClaim` formal schema reliably rather than returning bespoke nested JSONs.

### Task 1.3: Build Pipeline Hydrator & Validator
* **Target Outcome:** Normalize → Validate → Hydrate → Log is a formally owned sequence.
* **Location:** `backend/pipeline/hydration_engine.py` (New file)
* **Complexity:** HIGH
* **Description:** Scaffold middleware that intercepts data post-normalization, validates against expected models, and hydrates critical context (like existing identity/inventory linkages) before feeding the assembled package to intelligence nodes. 

### Task 1.4: Refactor Async Triggers
* **Target Outcome:** Async operations brought inside the structural contract.
* **Location:** `backend/routes/intel_routes.py`, `backend/routes/logistics.py`
* **Complexity:** MEDIUM
* **Description:** Wrap `trigger_gmail_scan` and `update_location` in the new Validation/Hydration engine. Hard failure conditions must be returned to the client rather than falling blindly into background execution tasks.

---

## 3. PHASE 2 TASK BREAKDOWN: Claim and Question System

### Task 2.1: Establish Claims Table
* **Target Outcome:** A claims table where all extractions land before touching canonical state.
* **Location:** `backend/scripts/setup_bq_claims.py` (New script)
* **Complexity:** LOW
* **Description:** Provision a new BigQuery table `extraction_claims` mapped to the Pydantic schema from Phase 1. 

### Task 2.2: Implement Conflict Detection Engine
* **Target Outcome:** Conflict detection at the claims layer generating events, avoiding silent overwrites.
* **Location:** `backend/pipeline/conflict_detector.py` (New file)
* **Complexity:** HIGH
* **Description:** Implement a processing queue that compares inbound `extraction_claims` against active canonical metrics in `entity_facts`. If contradiction exists outside of bounds, generate a HITL/OpenQuestion payload.

### Task 2.3: Upgrade Open Question Object Model
* **Target Outcome:** A formal Question object with owner, due time, downstream dependency list, resolution state, lineage pointer.
* **Location:** `backend/database/open_questions.py`
* **Complexity:** MEDIUM
* **Description:** Add `dependency_list` and `lineage_pointer` architecture to the existing schema. Plumb default policy configurations so that SLAs map correctly automatically.

### Task 2.4: Consolidate ASK Forks
* **Target Outcome:** All current ASK forks converge on the Question object model.
* **Location:** `backend/routes/chat_stream.py`, `backend/agents/iea_agent.py`
* **Complexity:** HIGH
* **Description:** Redesign the IEA interface so that `INCOMPLETE` statuses trigger a programmatic call to `raise_open_question` rather than routing ephemeral socket replies utilizing raw prompt history. 

### Task 2.5: Integrate Policy Engine Thresholds
* **Target Outcome:** ASK vs PROCEED criteria externalized to policy registry entries.
* **Location:** `backend/agents/attention_dispatcher.py` AND `backend/agents/iea_agent.py`
* **Complexity:** MEDIUM
* **Description:** Refactor system logic so `AttentionDispatcher` queries `policy_engine.py` for its SMS routing threshold (>7) and `IEA/HITL` checks global confidence rules before routing.

---

## 4. PHASE 3-5 READINESS FLAGS

### PHASE 3: Intelligence Consolidation
* **Requirements to Begin:** Phase 1 (Hydration Engine in production) and Phase 2 (Extraction Claims/Conflict Detection active) must be fully online.
* **Current Readiness:** **NOT READY.** The system still relies heavily on bespoke intelligence nodes routing off raw inputs via websocket strings.

### PHASE 4: Policy Registry Completion
* **Requirements to Begin:** Phase 2 Task 2.5 must be completed, ensuring nodes actually look for policies before acting. Standardized taxonomy required.
* **Current Readiness:** **PARTIAL.** The `policy_engine.py` is robust and cached, and the HITL interface natively leverages it. Needs universal coverage across AI nodes.

### PHASE 5: Meta Layer Readiness
* **Requirements to Begin:** Complete decoupling of operations from direct table modifications to utilize the Event Spine strictly.
* **Current Readiness:** **PARTIAL.** The meta-security logic (`/api/security/`) has been deployed. The `system_freeze` and `TokenAuth` features actively guard operations, effectively paving the immediate runway for external API integration.

---

## 5. RISK FLAGS

* **WebSocket UX Degradation:** Moving the IEA string-clarification phase (Phase 2.4) behind a rigid `OpenQuestion` database object risks adding significant UI latency to the frontend's previously instantaneous "Agentic Router" replies. Ensure WebSocket optimistic UI patterns accommodate database polling.
* **In-Place Mutation Conflicts:** The current Logistics `update_location` and Inventory `promote_vehicle` routes employ instant `UPDATE` queries against target tables before registering the events. Transitioning to a strict "Event Spine -> Projection" model during the Retrofit might break the frontend states displaying static React component values.

---

## 6. RECOMMENDED FIRST TASK

**Task 1.1: Define Universal Claims Schema (`backend/models/claims.py`)**

**Rationale:** The core deficiency in ensuring "Intelligence fires after structure, never instead of it" stems from not having a defined structural container for the AI's output. Introducing this model requires zero teardown of existing paths, takes minimal time (Low Complexity), and establishes the rigid target standard for testing the Phase 1 refactoring of `gmail_intel` and `attachment_processor`.
