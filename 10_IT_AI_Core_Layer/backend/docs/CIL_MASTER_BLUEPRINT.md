# AutoHaus CIL Master Blueprint

## SECTION 1: SYSTEM IDENTITY
Current version: C-OS v3.1.1-Alpha
GitHub HEAD: 0d94794
Replit URL: https://autohaus-command.replit.app
Backend: FastAPI port 5000
Frontend: React C-OS UI
Last verified: 2026-03-01

## SECTION 2: GOVERNING DOCTRINE
1. Precision information system, not automation engine.
2. Event spine is truth. Tables are projections.
3. Structure runs first: normalize → validate → hydrate → log.
4. Intelligence fires after structure, never instead of it.
5. Intelligence has two jobs: detect gaps, detect significance.
6. No significance scoring on raw strings.
7. Every intelligent node ends in ASK or PROCEED. Criteria are policy-defined.
8. If ASK, it becomes an operational object with owner, due time, and resolution path.
9. All material conflicts go to HITL. Immaterial conflicts within policy-defined tolerance log and proceed. The system prepares humans to decide, it does not decide.
10. If a conclusion changes downstream behavior, it must be logged durably or it is treated as UI-only and non-authoritative.
11. Structural hygiene precedes significance detection. Significance detection without hydration is invalid.
12. Human-provided information enters as HUMAN_ASSERTED. Verifiable facts require specific documentary evidence to reach VERIFIED. Intent and context require a supporting evidence structure to reach CORROBORATED. Every document ingestion checks both the PENDING_VERIFICATION queue for exact matches and the PENDING_CORROBORATION queue for supporting evidence accumulation. Contradictions in either queue surface to HITL with the stated assertion and the conflicting evidence presented together.

## SECTION 3: ARCHITECTURE INVARIANTS
### Core Interaction Invariants
* All system operations must be documented as independent, composable commands.
* The React frontend is a dumb terminal; the FastAPI backend holds all truth.
* No implicit state; all state must be explicitly serialized and synchronized.
* Database structure is canonical; the AI layer maps to it, it does not bend it.
* Every operation must cleanly succeed or yield a structured error—no silent failures.
* Data streams must handle concurrency cleanly; the system expects parallel inputs.

### Doctrine Rule 12 Invariant
* Human-provided information enters as HUMAN_ASSERTED. Verifiable facts require specific documentary evidence to reach VERIFIED. Intent and context require a supporting evidence structure to reach CORROBORATED. Every document ingestion checks both the PENDING_VERIFICATION queue for exact matches and the PENDING_CORROBORATION queue for supporting evidence accumulation. Contradictions in either queue surface to HITL with the stated assertion and the conflicting evidence presented together.

## SECTION 4: PHASE COMPLETION STATUS

### Phase 1: COMPLETE
* **Task 1.1: Define Universal Claims Schema**
  - Commit hashes: 81f9d1e (ExtractedClaim), ab654c4 (HumanAssertion)
* **Task 1.2: Standardize Async Extraction Nodes**
  - Commit hash: 81f9d1e
* **Task 1.3: Build Pipeline Hydrator & Validator**
  - Commit hash: 0ff9ef4
* **Task 1.4: Refactor Async Triggers**
  - Commit hash: 0d94794

**Outstanding Items & Phase 2 Dependencies:**
- Hydration Engine First Seed Validation: Dependent on downstream data structure ingestion mapped to Phase 2.
- Replit UI Projection Wait-State: Wait for Replit UI confirmation before removing direct table writes logical overlaps on Event Spine.
- Database Staging: Missing physical staging tables for `human_assertions` and `extraction_claims` (Phase 2 Task 2.1).

### Phase 2: IN PROGRESS
* **Task 2.1: Establish Claims Table** - NOT STARTED
* **Task 2.2: Implement Conflict Detection Engine** - NOT STARTED
* **Task 2.3: Upgrade Open Question Object Model** - NOT STARTED
* **Task 2.4: Consolidate ASK Forks** - NOT STARTED
* **Task 2.5: Integrate Policy Engine Thresholds** - NOT STARTED

### Phase 3: NOT READY
**Readiness Criteria:**
- Claims table has processed 500 real extractions without schema violations.
- Conflict detector has surfaced 20 genuine material conflicts safely to HITL.
- Hydration engine has assembled context packages for 1,000 sequential inputs with zero fallback-only results (proving entity matching succeeds).
- All three VIOLATED doctrine rules (Rules 3, 4, 11) confirmed COMPLIANT by a post-Phase 2 re-audit.

### Phase 4: PARTIAL READINESS
* Note policy_engine.py exists and is robust.
* Note what remains for full coverage: Implementation and query validation to enforce strict usage across components (e.g. AttentionDispatcher, IEA/HITL via Task 2.5).

### Phase 5: PARTIAL READINESS
* Note /api/security/ is deployed.
* Note what remains for upstream connection: Complete decoupling of operations from direct table modifications to utilize the Event Spine strictly.

## SECTION 5: FILE AND MODEL INVENTORY

* `backend/models/claims.py`
  - **Purpose:** Strict structural wrapper standardizing what shape extracted machine and human assertions must conform to.
  - **Key Models:** `ExtractedClaim`, `HumanAssertion`, `AssertionType`, `VerificationStatus`
  - **Commit Hash:** 81f9d1e (Init), ab654c4 (Added HumanAssertion)

* `backend/models/insurance.py`
  - **Purpose:** Pydantic entity schema dictating bounds for cross-domain unified insurance properties.
  - **Key Models:** `InsurancePolicy`, `PolicyStatus`
  - **Commit Hash:** 0ff9ef4

* `backend/pipeline/hydration_engine.py`
  - **Purpose:** Contextual gap and entity linker querying BQ metadata footprints to inform downstream AI components.
  - **Key Models:** `HydrationEngine`, `ContextPackage`
  - **Commit Hash:** 0ff9ef4 (Init), 0d94794 (Update payload validation)

* `backend/docs/HYDRATION_PACKAGE_SPEC.md`
  - **Purpose:** Field-level technical specification definition for the Hydration Engine variables and queries.
  - **Key Models:** N/A (Documentation Schema)
  - **Commit Hash:** 4f9a733 (Init), ab654c4 (Added human_assertions schema payload)

* `backend/docs/CIL_RETROFIT_PLAN.md`
  - **Purpose:** Foundational review mapping Doctrine gaps against target codebase task allocations.
  - **Key Models:** N/A (Architecture Doc)
  - **Commit Hash:** 5fa12c1 (Init), ab654c4 (Added Doctrine Rule 12)

## SECTION 6: OUTSTANDING VALIDATION FLAGS
1. **Hydration engine BigQuery integration validation pending first seed**
   - *Needs to happen:* Pipeline processing against real extraction load to confirm proper contextual BQ queries.
   - *Blocked on:* First live seed ingestion yielding true records against known VINs/Emails.
   - *Resolved by:* System operation tests hitting hydration payloads directly connecting to live inputs.
2. **Replit UI projection confirmation pending before mutation inversion**
   - *Needs to happen:* Verify React dashboard state hooks successfully read projected state without breaking visual updates.
   - *Blocked on:* Replit architecture side bridging verification loops.
   - *Resolved by:* Replit team confirmation inside task syncs.
3. **human_assertions table not yet provisioned**
   - *Needs to happen:* BigQuery script deployment for `human_assertions` DDL.
   - *Blocked on:* Phase 2 rollout structure.
   - *Resolved by:* Antigravity engineering provisioning payloads.
4. **extraction_claims table not yet provisioned**
   - *Needs to happen:* BigQuery script deployment for `extraction_claims` DDL.
   - *Blocked on:* Task 2.1 initiation.
   - *Resolved by:* Antigravity handling Task 2.1 script execution.

## SECTION 7: AUTHORITY AND EVIDENCE HIERARCHY

**Full Hierarchy:**
MASTER > SOVEREIGN > HUMAN_ASSERTED > VERIFIED > AUTO_ENRICHED > EXTRACTED > PROPOSED > UNVERIFIED

**Evidence Tiers:**
- TIER 1: Primary legal, state, or absolute source documents (Operating agreements, Secretary of State filings, official IDs).
- TIER 2: Processed third-party documents tied to entities (Insurance declarations, banking statements, signed contracts).
- TIER 3: Routine operational records (Invoices, emails, internal logging traces).

**HumanAssertion Types:**
- VERIFIABLE_FACT (requires pointer to specific documentary evidence to reach VERIFIED)
- INTENT (requires a supporting evidence structure to reach CORROBORATED)
- CONTEXT (requires a supporting evidence structure to reach CORROBORATED)

## SECTION 8: AGENT BOUNDARIES
* Antigravity owns: `backend/`, `scripts/`, `auth/`, `agents/`, `memory/`, `pipeline/`, `models/`
* Replit owns: `frontend/`
* GitHub main is the only handoff point.
* Neither agent touches the other's directory.
* Credentials injected by Moaz only.

## SECTION 9: COORDINATION FLAGS ACTIVE
* **Flag 1: Task 2.4 IEA ASK fork consolidation**
  - **Blocked on:** Replit optimistic UI pattern confirmation.
  - **Do not begin until:** Replit confirms question object WebSocket pattern is ready.
* **Flag 2: Mutation order inversion on promote_vehicle and update_location**
  - **Blocked on:** Replit frontend state reads confirmed projection-ready.
  - **Do not begin until:** Replit confirms React components read from projected state not direct table mutation.

## SECTION 10: TEST SPECIFICATION SUMMARY

* **Tier A — Seed with known gaps:**
  - Introduce structural seed mapping intentionally omitting required VIN correlations and EIN configurations to verify the `IEA` correctly surfaces structured questions indicating recognized boundaries.
* **Tier B — Feed confirming evidence:**
  - Push matching missing documents (e.g. KAMM Operating Agreement) validating against active `OpenQuestions` effectively bridging previous Tier A gaps to verify loop closure mapping and transition towards `VERIFIED` authority flags.
* **Tier C — Introduce contradicting evidence:**
  - Ingest conflicting evidence models explicitly contravening previously established `VERIFIED` invariants (e.g. AstroLogistics property policies overlapping active bounds) locking pipeline insertion mechanics enforcing the `conflict_detector.py` to route up an appropriate context payload cleanly into HITL environments instead of natively applying mutations.

**Key withhold items for testing:**
- KAMM LLC operating agreement
- Vehicle VINs for 11 stub records
- KAMM dealer license document
- Auto-Owners binding confirmation
- Next Gig LLC formation documents

## SECTION 11: OPEN QUESTIONS PENDING HUMAN RESOLUTION
1. Policy 66465558 vs KammLLCTPP-6041894 — same instrument or separate?
2. Grinnell Mutual overlap with Auto-Owners — intentional dual coverage or replacement?
3. Next Gig LLC — EIN, registered address, formation state, principal person
4. AstroLogistics EIN — not found in documents
5. Asim contact information — email and phone
6. Mohsin contact information — email and phone
7. Vehicle VINs for 11 stub inventory records
8. Legal owning entity confirmation for current inventory vehicles
9. Workers Comp and EPLI policy details for Carbon LLC
10. Fleet and Logistics policy details for Fluiditruck and Carlux

## SECTION 12: PHASE 2 TASK SPECIFICATIONS

### Task 2.1: Establish Claims Table
*Target Outcome:* A claims table where all extractions land before touching canonical state.
*Location:* `backend/scripts/setup_bq_claims.py` (New script)
*Complexity:* LOW
*Description:* Provision a new BigQuery table `extraction_claims` mapped to the Pydantic schema from Phase 1. 

### Task 2.2: Implement Conflict Detection Engine
*Target Outcome:* Conflict detection at the claims layer generating events, avoiding silent overwrites.
*Location:* `backend/pipeline/conflict_detector.py` (New file)
*Complexity:* HIGH
*Description:* Implement a processing queue that compares inbound `extraction_claims` against active canonical metrics in `entity_facts`. If contradiction exists outside of bounds, generate a HITL/OpenQuestion payload.

### Task 2.3: Upgrade Open Question Object Model
*Target Outcome:* A formal Question object with owner, due time, downstream dependency list, resolution state, lineage pointer.
*Location:* `backend/database/open_questions.py`
*Complexity:* MEDIUM
*Description:* Add `dependency_list` and `lineage_pointer` architecture to the existing schema. Plumb default policy configurations so that SLAs map correctly automatically.

### Task 2.4: Consolidate ASK Forks
*Target Outcome:* All current ASK forks converge on the Question object model.
*Location:* `backend/routes/chat_stream.py`, `backend/agents/iea_agent.py`
*Complexity:* HIGH
*Description:* Redesign the IEA interface so that `INCOMPLETE` statuses trigger a programmatic call to `raise_open_question` rather than routing ephemeral socket replies utilizing raw prompt history. *(Flagged: Replit coordination required first)*

### Task 2.5: Integrate Policy Engine Thresholds
*Target Outcome:* ASK vs PROCEED criteria externalized to policy registry entries.
*Location:* `backend/agents/attention_dispatcher.py` AND `backend/agents/iea_agent.py`
*Complexity:* MEDIUM
*Description:* Refactor system logic so `AttentionDispatcher` queries `policy_engine.py` for its SMS routing threshold (>7) and `IEA/HITL` checks global confidence rules before routing.

## SECTION 13: POLICY REGISTRY INVENTORY (SEEDED TASK 2.5)
The following keys are actively queried by system nodes.

DOMAINS:
**PIPELINE**
* `critical_fields`: Fields where any variance triggers CRITICAL severity. Evaluated by Conflict Detector. Value: `["ein", "vin", "policy_number", "ownership_pct", "license_number"]`
* `conflict_tolerance_VEHICLE_price`: Allowed price variance as decimal fraction. Value: `0.05`
* `conflict_tolerance_PERSON_email`: Exact match required. Value: `0.0`
* `conflict_tolerance_ENTITY_ein`: Exact match required. Value: `0.0`
* `question_sla_hours_CONFLICT`: Hours before conflict question is overdue. Value: `24`
* `question_sla_hours_ASSERTION`: Hours before assertion question is overdue. Value: `72`
* `question_sla_hours_IEA`: Hours before IEA clarification question is overdue. Value: `4`
* `question_sla_hours_MANUAL`: Hours before manually created question is overdue. Value: `48`

**AGENTS**
* `attention_sms_threshold`: Urgency score at or above which SMS is triggered instead of WebSocket. Consumed by AttentionDispatcher. Value: `7`
* `attention_urgency_scale`: Urgency score bands and their operational meaning. Consumed by AttentionDispatcher.
* `iea_confidence_threshold`: Minimum confidence score for IEA to classify a command as COMPLETE. Consumed by IEA Agent. Value: `0.7`
* `iea_required_fields_INVENTORY`: Fields IEA requires for INVENTORY commands. Value: `["vin", "entity"]`
* `iea_required_fields_FINANCE`: Fields IEA requires for FINANCE commands. Value: `["entity", "time_period"]`
* `iea_required_fields_LOGISTICS`: Fields IEA requires for LOGISTICS commands. Value: `["driver_id", "vehicle_id"]`
* `iea_required_fields_SERVICE`: Fields IEA requires for SERVICE commands. Value: `["vin", "service_type"]`
* `iea_required_fields_CRM`: Fields IEA requires for CRM commands. Value: `["contact_identifier"]`
* `iea_required_fields_COMPLIANCE`: Fields IEA requires for COMPLIANCE commands. Value: `["entity", "document_type"]`
