# CLAIMS_AND_EVENTS_CANON.md
**AutoHaus CIL — Canonical Reference: Claims, Events, Truth Status, Projections**
Version: 1.1 | March 2, 2026
Status: GOVERNING — do not modify without SOVEREIGN approval and version increment

This document is one of three governing references for the AutoHaus C-OS.
The other two are:
- CIL_THREE_LAYER_ARCHITECTURE.md v1.1 (doctrine)
- MASTER_SUMMARY.md (narrative, non-governing)

If this document conflicts with MASTER_SUMMARY.md, this document wins.
If this document conflicts with CIL_THREE_LAYER_ARCHITECTURE.md, raise it.

---

## Section 1: Event Spine Declaration

### The Single Source of Truth for Events

**cil_events is the event spine.**

Every pipeline stage, every state change, every CIL decision emits a durable event to cil_events.
This is the complete, ordered story of everything that has happened in the system.
Append-only. Never modified after write.

BigQuery: autohaus-infrastructure.autohaus_cil.cil_events

**system_audit_ledger is the regulated compliance projection.**

system_audit_ledger is a filtered, structured projection of cil_events built for three specific
consumers: insurance audit trails, FTC/GLBA 10-year retention compliance, and Iowa regulatory
review. It contains the subset of events that carry legal or insurance significance, formatted
for those consumers.

BigQuery: autohaus-infrastructure.autohaus_cil.system_audit_ledger

**Rule:** Nothing writes directly to system_audit_ledger. It is populated by a projection
pipeline that reads from cil_events. Code that writes to system_audit_ledger directly is
violating doctrine.

### Core State Tables Are Read Models

inventory_master, deals, open_questions, extraction_claims, and human_assertions are
operational read models. Services may write to them directly for performance. However:

  - Every mutation to a core state table MUST emit a corresponding cil_events entry.
  - cil_events is the canonical reconstruction path. If a state table is corrupted or
    rebuilt, cil_events is authoritative.
  - Treating inventory_master or deals as primary truth without a corresponding event
    in cil_events is a doctrine violation.

### Table Classification

Two categories. Do not blur them.

Operational read models (written by services, must be event-complete):
  extraction_claims, human_assertions, open_questions, inventory_master, deals,
  compliance_log, master_person_graph

Regulatory and analytics projections (derived from events and/or read models,
never written directly):
  system_audit_ledger, pending_verification_queue, open_questions_dashboard,
  inventory_health_snapshot, contracts_in_transit, compliance_timeline

### Event Spine Schema

cil_events table:

  event_id          STRING    NOT NULL   UUID, primary key
  event_type        STRING    NOT NULL   See Event Type Registry below
  entity_id         STRING    NOT NULL   Primary business object this event concerns
  entity_type       STRING    NOT NULL   VEHICLE | PERSON | ENTITY | DOCUMENT | DEAL |
                                         POLICY | CLAIM | QUESTION
  session_id        STRING    NULLABLE   Present when event originates from a human session
  actor_id          STRING    NULLABLE   User ID of the person or agent who caused this event
  correlation_id    STRING    NULLABLE   Ties multiple events emitted in one pipeline run
  parent_event_id   STRING    NULLABLE   The event that triggered this event, if applicable
  emitted_by        STRING    NOT NULL   The pipeline component that emitted this event
  authority         STRING    NOT NULL   Authority level of the actor — see Section 2
  payload           JSON      NOT NULL   Event-specific structured data
  created_at        TIMESTAMP NOT NULL   UTC, set at write time, never modified

### Event Type Registry

Pipeline events:
  DOCUMENT_INGESTED           Document received by intake pipeline
  DOCUMENT_CLASSIFIED         Document type determined
  CLAIMS_EXTRACTED            ExtractedClaim objects written to extraction_claims
  CONFLICT_DETECTED           Conflict detector found a material discrepancy
  GAP_DETECTED                Conflict detector found a required field is missing
  EXTRACTION_FAILED           Gemini extraction returned unusable output

Question and resolution events:
  QUESTION_CREATED            New open question written to open_questions
  QUESTION_ASSIGNED           Owner role assigned or reassigned
  QUESTION_ANSWERED           Human provided an answer
  QUESTION_RESOLVED           Question closed, assertion updated
  QUESTION_ESCALATED          SLA exceeded, escalation triggered
  DEPENDENCY_RELEASED         A blocked question became unblocked

State change events:
  VEHICLE_STATUS_UPDATED      inventory_master status field changed
  ENTITY_TRANSFER             Vehicle moved from one LLC to another
  DEAL_STATE_CHANGED          Deal lifecycle state transition
  TITLE_STATUS_UPDATED        Title receipt or status change recorded
  ASSERTION_VERIFIED          HumanAssertion moved to VERIFIED authority
  ASSERTION_REJECTED          HumanAssertion rejected, question reopened

Policy and compliance events:
  THRESHOLD_APPROACHING       A policy threshold is within warning range
  THRESHOLD_BREACHED          A policy threshold has been crossed
  COMPLIANCE_ALERT            Iowa title deadline, licensing, or regulatory event
  CASHFLOW_ALERT              Contracts in Transit aged past policy threshold
  INSURANCE_EXPOSURE_ALERT    Total lot value approaching or exceeding insurance ceiling
  COVERAGE_STATUS_LOGGED      Coverage status at time of event
  HARD_STOP_ENFORCED          Membrane blocked an action due to policy breach

Communication and approval events:
  OUTBOUND_SMS_SENT               Twilio SMS dispatched
  REPAIR_AUTHORIZATION_RECEIVED   Customer approved repair
  COMMUNICATION_CERTIFICATE_GENERATED  PDF proof of approval created
  WALKAROUND_UPLOADED             Proof-of-damage video received
  QUOTE_VIEWED                    Customer opened a /quote/:uuid link
  QUOTE_APPROVED                  Customer digitally signed

Governance events:
  ENRICHMENT_PROPOSED         AI proposed a business action, awaiting approval
  ENRICHMENT_APPROVED         Human approved an AI-proposed action
  ENRICHMENT_REJECTED         Human rejected an AI-proposed action
  OVERRIDE_LOGGED             SOVEREIGN used management override, reason recorded
  HARD_STOP_OVERRIDDEN        SOVEREIGN overrode a hard stop, reason required

---

## Section 2: Truth Status and Authority Hierarchy

### Authority Levels (ranked highest to lowest)

  MASTER
    Set by Moaz or Kamran at system design time. Reserved for structural facts
    about entities and ownership that define the business ontology.
    Example: "Carbon LLC is the MSO."

  SOVEREIGN
    Set by SOVEREIGN-access users (Ahsin, Moaz, Kamran) via the C-OS.
    Human-confirmed, high-trust operational facts.
    Example: "This vehicle's title has been received."

  VERIFIED
    Human-asserted fact corroborated by documentary evidence reviewed by a
    SOVEREIGN or STANDARD user.
    Example: "AstroLogistics EIN confirmed against IRS letter."

  COMPLIANCE_VERIFIED
    Special class of VERIFIED. Confirmed through a compliance-specific process.
    Example: "Form 8300 filed for deal #D-2026-0047."

  AUTO_ENRICHED
    Written by the CIL extraction pipeline AFTER human approval of the enrichment
    action. Sandbox-first: proposed first, approved second.
    AUTO_ENRICHED is strictly post-approval. It is never assigned before approval.
    Pre-approval writes carry PROPOSED authority.

  EXTRACTED
    Raw output from Gemini extraction pipeline. Not yet human-reviewed.
    Always paired with a confidence score. Treated as a claim, not a fact,
    until elevated by human review.

  PROPOSED
    CIL or AI agent has proposed this fact based on inference or pattern matching,
    OR an internal write is pending human approval before it becomes AUTO_ENRICHED.
    Not yet extracted from a source document and not yet approved.

  UNVERIFIED
    Lowest trust. Received from an unverified external source, or flagged as
    potentially conflicting with higher-authority facts.

### Truth Status Vocabulary

Used in extraction_claims, human_assertions, and anywhere a fact is stored:

  ADVISORY
    Informational. Does not require action. Logged for context.

  ASSERTED
    A human or system has stated this as true. Not yet corroborated.
    Must carry the asserting authority level.

  VERIFIED
    Corroborated by documentary evidence reviewed by an authorized person.

  COMPLIANCE_VERIFIED
    Verified through a compliance-specific process (Iowa DOT, IRS, FTC).

  LOCKED
    Immutable. Set by MASTER authority. Cannot be overridden without
    a SOVEREIGN consensus event in cil_events.

  PENDING_VERIFICATION
    Asserted but awaiting corroboration. Has a linked open question.

  STUB_PENDING_VIN
    Vehicle record exists but VIN is not yet known.

  STUB_PENDING_CONTACT
    Person record exists but contact details (email, phone) are not yet known.

  STUB_PENDING_DOCUMENT
    Entity or fact record exists but the source document has not been received.
    Use this for "STUB" cases in the unresolved facts list.

  PENDING_DOCUMENTARY_VERIFICATION
    Asserted verbally or operationally. Documentary proof not yet received
    and reviewed.

  CONFLICT
    Two or more sources assert different values for this field.
    Requires open question resolution before this fact can be used.

### How Truth Status Is Applied

Every fact stored in the system carries:
  extracted_value or asserted_value   The value itself
  authority                           From the hierarchy above
  truth_status                        From the vocabulary above
  confidence                          Float 0.0-1.0 (EXTRACTED); 1.0 for VERIFIED and above
  source_lineage                      What produced or asserted this fact
  verified_by and verified_at         Who and when, for VERIFIED and above

Example — "AstroLogistics LLC holds vehicle titles":
{
  "asserted_value": "AstroLogistics LLC",
  "target_field": "title_holding_entity",
  "authority": "SOVEREIGN",
  "truth_status": "ASSERTED",
  "confidence": 1.0,
  "source_lineage": "verbal_assertion_moaz_20260301",
  "verified_by": null,
  "notes": "Documentary verification pending. KAMM LLC operating agreement not yet reviewed."
}

Example — "Next Gig LLC holds 50% of KAMM LLC":
{
  "asserted_value": "50%",
  "target_field": "kamm_ownership_next_gig",
  "authority": "SOVEREIGN",
  "truth_status": "PENDING_DOCUMENTARY_VERIFICATION",
  "confidence": 0.85,
  "source_lineage": "verbal_assertion_moaz_20260228",
  "notes": "Next Gig LLC formation documents withheld for testing."
}

---

## Section 3: Claims Contract

### ExtractedClaim Schema

The ExtractedClaim is the atomic unit of intelligence output.
Every fact the CIL learns from a document is an ExtractedClaim.

  claim_id            STRING    UUID, primary key
  source              STRING    ClaimSource: MEDIA | EMAIL | WEBHOOK | MANUAL
  extractor_identity  STRING    Pipeline component that produced this claim
  input_reference     STRING    File ID, email ID, or webhook payload ID
  source_lineage      JSON      Model used, timestamp, temperature, stub_type if applicable
  entity_type         STRING    VEHICLE | PERSON | VENDOR | DOCUMENT | UNKNOWN
  target_field        STRING    The field this claim is asserting a value for
  extracted_value     STRING    The value itself, always a string, consumer casts
  confidence          FLOAT     0.0 to 1.0
  authority           STRING    Always EXTRACTED at creation. Elevated by human review.
  truth_status        STRING    Always EXTRACTED at creation. Elevated by resolution.
  created_at          TIMESTAMP UTC, set at write
  resolved_at         TIMESTAMP Nullable. Set when elevated to VERIFIED or rejected.
  resolved_by         STRING    Nullable. User ID of reviewer.
  open_question_id    STRING    Nullable. Set if this claim generated a question.

### Sentinel Values

Sentinels are reserved extracted_value strings with specific field constraints and
required downstream behaviors. They are not general-purpose.

  VIN_NOT_PROVIDED
    Permitted only when target_field = "vin"
    Used when the document explicitly states the VIN is unknown or not provided.
    source_lineage.stub_type must be set to "STUB_PENDING_VIN"
    Required downstream behavior: automatically create STUB_PENDING_VIN open question.
    Must block any external effects (listing, entity transfer) on this vehicle until resolved.

  ENTITY_NAME_MISMATCH
    Permitted only when target_field = "entity_id" or "entity_name" resolution
    Used when the extracted entity name does not match any registered entity in
    business_ontology.json.
    Required downstream behavior: automatically create ENTITY_VERIFICATION open question.
    Must block invoice booking and any intercompany billing until resolved.

### HumanAssertion Schema

A HumanAssertion is a fact stated directly by an authorized human, not extracted from a document.

  assertion_id             STRING    UUID, primary key
  asserted_by              STRING    User ID of asserting person
  asserted_at              TIMESTAMP UTC
  authority                STRING    Authority level of asserting person
  target_entity_id         STRING    The business object this assertion concerns
  target_entity_type       STRING    VEHICLE | PERSON | ENTITY | POLICY | DEAL
  target_field             STRING    The field being asserted
  asserted_value           STRING    The value
  truth_status             STRING    ASSERTED at creation. VERIFIED when corroborated.
  verification_status      STRING    PENDING | VERIFIED | REJECTED |
                                     PENDING_DOCUMENTARY_VERIFICATION
  corroborating_document   STRING    Nullable. Document ID that verifies this assertion.
  open_question_id         STRING    Nullable. Linked open question if verification pending.
  notes                    STRING    Nullable. Context or caveats.

### Conflict Resolution Rules (Survivorship)

When two claims assert different values for the same field on the same entity:

1. Higher authority wins: VERIFIED > AUTO_ENRICHED > EXTRACTED
2. Same authority, different values: more recent wins, but CONFLICT_DETECTED is logged
3. SOVEREIGN assertion vs EXTRACTED claim: SOVEREIGN wins, EXTRACTED marked SUPERSEDED,
   event logged
4. Two EXTRACTED claims conflict: neither wins, open question created, both held as CONFLICT
5. LOCKED facts cannot be superseded by anything below MASTER authority

---

## Section 4: Open Questions Contract

### OpenQuestion Schema

  question_id       STRING    UUID, primary key
  question_text     STRING    Human-readable question for the C-OS interface
  owner_role        STRING    SOVEREIGN | STANDARD | FIELD
  status            STRING    OPEN | BLOCKED | ANSWERED | RESOLVED | ESCALATED
  priority          STRING    CRITICAL | HIGH | MEDIUM | LOW
  created_at        TIMESTAMP UTC
  due_at            TIMESTAMP SLA deadline, computed from policy registry
  resolved_at       TIMESTAMP Nullable
  resolved_by       STRING    Nullable, user ID
  resolution_text   STRING    Nullable, what the human said
  lineage_pointer   STRING    claim_id or assertion_id that triggered this question
  dependency_list   ARRAY     question_ids this question is blocked by
  blocks_list       ARRAY     question_ids or action_ids blocked by this question
  entity_id         STRING    Business object this question concerns
  entity_type       STRING    VEHICLE | PERSON | ENTITY | POLICY | DEAL

### Ask vs. Proceed Policy

ALWAYS ASK — never proceed autonomously:
  - Entity name on invoice does not match any registered entity in business_ontology.json
  - VIN is explicitly stated as not provided
  - Two EXTRACTED claims conflict on the same field
  - Vehicle entity transfer would trigger intercompany billing
  - SOVEREIGN assertion conflicts with a document
  - Insurance policy field is PENDING_DOCUMENTARY_VERIFICATION and an event references it

PROCEED AUTONOMOUSLY — log to cil_events as ADVISORY:
  - Extracting line items from a vendor invoice where entity is confirmed
  - Classifying a document type when confidence > 0.85 and type is unambiguous
  - Computing days_in_stock from known date_in_stock
  - Routing inbound SMS to correct staff member via identity resolution

PROCEED BUT REQUIRE APPROVAL before any write with external effect:
  - Sending outbound SMS to a customer
  - Publishing a vehicle listing to public inventory
  - Generating an intercompany invoice
  - Any DealerCenter push via Membrane C

### Authority During the Approval Window

Before approval:   internal writes carry PROPOSED authority
After approval:    authority is elevated to AUTO_ENRICHED

AUTO_ENRICHED is never assigned before approval. There is no "AUTO_ENRICHED pending approval."
Pre-approval state is always PROPOSED. This prevents approved-ness laundering.

---

## Section 5: Projections Registry

Nothing writes to these directly. All are derived from cil_events and/or operational read models.

  system_audit_ledger
    Source: cil_events (insurance and compliance event types only)
    Consumer: Insurance audits, FTC/GLBA retention, Iowa DOT
    Refresh: Projection pipeline, idempotent writes keyed by event_id
             May be streaming or scheduled — idempotency is required either way

  pending_verification_queue
    Source: extraction_claims WHERE truth_status IN (EXTRACTED, CONFLICT)
    Consumer: C-OS Action Center, Anomaly Monitor
    Refresh: Materialized view

  open_questions_dashboard
    Source: open_questions + cil_events QUESTION_* events
    Consumer: C-OS Anomaly Alert Plate, Membrane A SLA enforcement
    Refresh: Materialized view

  inventory_health_snapshot
    Source: inventory_master + cil_events VEHICLE_* and THRESHOLD_* events
    Consumer: Inventory Master Plate, Capital Exposure Tracker
    Refresh: Scheduled, 30 minutes

  contracts_in_transit
    Source: deals WHERE deal_state = FUNDED AND days_since_funding > 0
    Consumer: Aged CIT Flag, CASHFLOW_ALERT events
    Refresh: Streaming append

  compliance_timeline
    Source: cil_events WHERE event_type IN (COMPLIANCE_ALERT, COVERAGE_STATUS_LOGGED,
            HARD_STOP_*)
    Consumer: Compliance Plate, Membrane C reporting
    Refresh: Streaming append

---

## Section 6: Policy Registry Defaults

Current configured values as of March 2, 2026.
These are registry entries, not constants.
Changing a policy value does not require a code deploy.
Changes require SOVEREIGN authorization and a cil_events entry.

Domain PIPELINE:
  extraction_temperature:               0.0
  extraction_min_confidence_threshold:  0.7
  vin_not_provided_sentinel:            "VIN_NOT_PROVIDED"
  stub_pending_vin_auto_question:       true
  entity_mismatch_auto_question:        true
  question_sla_critical_hours:          4
  question_sla_high_hours:              24
  question_sla_medium_hours:            72

Domain COMPLIANCE:
  iowa_title_deadline_days:             30
  iowa_title_warning_days:              7
  inventory_max_units:                  15
  inventory_warning_units:              13
  insurance_exposure_ceiling:           200000
  insurance_alert_threshold_80pct:      160000
  insurance_alert_threshold_90pct:      180000
  insurance_alert_threshold_95pct:      190000
  cit_aging_threshold_days:             5
  cit_warning_threshold_days:           3
  ftc_retention_years:                  10

Domain CHANNELS:
  cashflow_alert_channel:               SMS_SOVEREIGN_ALWAYS
  insurance_critical_channel:           SMS_AND_WEBSOCKET
  title_deadline_channel:               WEBSOCKET_IF_ACTIVE_ELSE_SMS
  anomaly_default_channel:              WEBSOCKET_ONLY
  hard_stop_channel:                    WEBSOCKET_BLOCK_WITH_UI_MESSAGE

---

## Section 7: Known Unresolved Facts (as of March 2, 2026)

Facts the system is operating on that are NOT yet VERIFIED.
Included here to prevent any governing document from treating them as settled.

  AstroLogistics LLC holds vehicle titles
    Authority: SOVEREIGN (verbal, Moaz)
    Truth status: ASSERTED
    Pending: KAMM LLC operating agreement review

  Next Gig LLC owns 50% of KAMM LLC
    Authority: SOVEREIGN (verbal, Moaz)
    Truth status: PENDING_DOCUMENTARY_VERIFICATION
    Pending: Next Gig LLC formation documents

  Auto-Owners policy is bound
    Authority: SOVEREIGN (verbal, Moaz)
    Truth status: PENDING_DOCUMENTARY_VERIFICATION
    Pending: Policy document not yet located

  Policy 66465558 vs KammLLCTPP-6041894 — same or separate instrument
    Authority: UNKNOWN
    Truth status: CONFLICT
    Open question #1

  Grinnell Mutual — dual coverage or replaced by Auto-Owners
    Authority: UNKNOWN
    Truth status: CONFLICT
    Open question #2

  AstroLogistics EIN
    Authority: UNKNOWN
    Truth status: STUB_PENDING_DOCUMENT
    Open question #4

  Asim email and phone
    Authority: UNKNOWN
    Truth status: STUB_PENDING_CONTACT
    Open question #5

  Mohsin email and phone
    Authority: UNKNOWN
    Truth status: STUB_PENDING_CONTACT
    Open question #6

  VINs for 11 stub vehicles
    Authority: UNKNOWN
    Truth status: STUB_PENDING_VIN
    Open question #7

  Workers Comp and EPLI details for Carbon LLC
    Authority: UNKNOWN
    Truth status: STUB_PENDING_DOCUMENT
    Open question #8

  Fleet and Logistics policy details for Fluiditruck and Carlux
    Authority: UNKNOWN
    Truth status: STUB_PENDING_DOCUMENT
    Open question #9

---

## Document Control

  Version  Date        Author                       Change
  1.0      2026-03-02  Moaz Sial / CIL Session      Initial governing draft
  1.1      2026-03-02  Moaz Sial / CIL Session      Seven-point tightening pass:
                                                     (A) Core state tables declared as
                                                     read models with event-complete
                                                     requirement. (B) Projection pipeline
                                                     clarified as idempotent, keyed by
                                                     event_id. (C) actor_id, correlation_id,
                                                     parent_event_id added to event schema.
                                                     (D) Table classification split into
                                                     operational read models vs regulatory
                                                     projections. (E) STUB_PENDING_CONTACT
                                                     and STUB_PENDING_DOCUMENT added to
                                                     truth status vocabulary. (F) PROPOSED
                                                     locked as pre-approval authority;
                                                     AUTO_ENRICHED strictly post-approval.
                                                     (G) Sentinel value field constraints
                                                     and required downstream behaviors
                                                     codified.

Next version requires: SOVEREIGN approval + increment to 1.2 + entry in this table.

---

AutoHaus · Carbon LLC · C-OS v3.1.1-Alpha
CLAIMS_AND_EVENTS_CANON.md v1.1 — GOVERNING DOCUMENT
