# AUTOHAUS CIL — PHASE 3 MEMBRANE BUILD BRIEF
**Issued to: Antigravity (Cursor — backend)**
Version: 1.0 | March 2, 2026
Status: ACTIVE — execute in sequence

Read these documents before writing a single line of code:
- backend/docs/CIL_THREE_LAYER_ARCHITECTURE.md v1.1 (doctrine)
- backend/docs/CLAIMS_AND_EVENTS_CANON.md v1.1 (ontology)

If any build decision conflicts with those documents, stop and raise it.
Do not resolve conflicts by guessing.

---

## What Phase 3 Is

Phase 3 builds Membrane A — the internal runtime enforcement layer
that sits between the CIL and the staff-facing C-OS interface.

The membrane does not exist yet as a proper layer. Components currently
labeled "membrane" are either running incorrectly inside the CIL or not
running at all. Phase 3 extracts them, rebuilds them correctly, and
wires them to the CIL via defined contracts.

The membrane's job in one sentence:
  Receive CIL conclusions. Enforce them against the current session.
  Deliver the result to the right channel. Log enforcement to cil_events.

The membrane never:
  - Evaluates policy (that is CIL's job)
  - Upgrades authority on any fact (that is CIL's job)
  - Creates truth (that is CIL's job)
  - Contains business logic that belongs in the CIL

The smell test for every function you write:
  Does it decide truth? → Wrong layer. Move to CIL.
  Does it enforce in-session? → Correct layer. Stay in membrane.
  Does it only render? → Wrong layer. Move to UI.

---

## Build Sequence

Build these five components in order. Do not start step N+1 until
step N is complete and tested. Each step has a verification hook.

---

### STEP 1 — Session Context Manager

File: backend/membrane/session_context.py

Purpose: Track who is active, what role they hold, what entity scope
they can see, and what has happened in this session.

The session context is the membrane's memory for a single interaction.
It is not persisted between sessions. It is not the same as
sovereign_memory (that is the CIL's vector vault for long-term context).

Data model:

```python
class SessionContext:
    session_id: str           # UUID, created at session start
    user_id: str              # From personnel_access_matrix
    role: str                 # SOVEREIGN | STANDARD | FIELD
    entity_scope: list[str]   # Entities this user can see
    active_entity: str        # Currently selected entity lens
    session_started_at: datetime
    last_activity_at: datetime
    pending_approvals: list[str]  # action_ids awaiting this user's approval
    active_hard_stops: list[str]  # policy breach ids currently blocking actions
```

Rules:
- Create a new SessionContext on every WebSocket connection
- Destroy it on disconnect
- Do not persist to BigQuery (session state is ephemeral)
- DO emit SESSION_STARTED and SESSION_ENDED events to cil_events
  (the events are durable; the context object is not)

Entity scope enforcement:
- SOVEREIGN: all entities
- STANDARD (Asim): KAMM_LLC, AUTOHAUS_SERVICES_LLC
- STANDARD (Mohsin): ASTROLOGISTICS_LLC, AUTOHAUS_SERVICES_LLC
- FIELD (Sunny): FLUIDITRUCK_LLC, CARLUX_LLC
- Entity scope is read from business_ontology.json at session start,
  not hardcoded here

Verification hook:
  Start a WebSocket session as each role. Assert that entity_scope
  matches the access matrix. Assert SESSION_STARTED appears in cil_events
  with correct actor_id and authority.

---

### STEP 2 — Policy Enforcement Layer

File: backend/membrane/policy_enforcer.py

Purpose: When CIL emits a significance-flagged event, the policy
enforcer decides what action to take in the current session. It calls
CIL policy evaluation and executes the enforcement workflow.

The policy enforcer does NOT evaluate the policy. It calls the CIL to
get the evaluation result and then enforces it.

Two enforcement modes:

HARD STOP
  Used when a policy threshold has been BREACHED and the action must
  be blocked entirely.
  
  Hard stops currently defined (from policy registry):
    - inventory_max_units: 15 — block any "move to inventory" action
    - insurance_exposure_ceiling: 200000 — block any new unit intake
  
  Hard stop enforcement flow:
    1. CIL emits THRESHOLD_BREACHED event
    2. Membrane receives event via internal subscription
    3. PolicyEnforcer adds breach to session_context.active_hard_stops
    4. Any action matching the breached threshold is blocked at membrane
    5. Membrane emits HARD_STOP_ENFORCED to cil_events with:
       actor_id, session_id, correlation_id, blocked_action, policy_key,
       current_value, threshold_value
    6. UI receives block message via MOUNT_PLATE: HARD_STOP

  SOVEREIGN override path:
    1. SOVEREIGN user issues override command with reason
    2. Membrane validates role is SOVEREIGN
    3. Membrane emits HARD_STOP_OVERRIDDEN to cil_events with reason
    4. Hard stop removed from active_hard_stops for this session
    5. Action is permitted to proceed
    6. Reason is required — membrane rejects override without reason text

APPROVAL GATE
  Used for sandbox-first governance: AI-proposed actions that require
  human approval before executing external effects.
  
  External effects requiring approval (from CLAIMS_AND_EVENTS_CANON.md):
    - Sending outbound SMS to a customer
    - Publishing a vehicle listing to public inventory
    - Generating an intercompany invoice
    - Any DealerCenter push via Membrane C
  
  Approval gate flow:
    1. CIL emits ENRICHMENT_PROPOSED event
    2. Membrane adds action to session_context.pending_approvals
    3. Membrane emits MOUNT_PLATE: APPROVAL_REQUIRED to UI
    4. User approves or rejects via UI
    5. On approval: membrane emits ENRICHMENT_APPROVED to cil_events,
       triggers the external effect, authority elevated to AUTO_ENRICHED
    6. On rejection: membrane emits ENRICHMENT_REJECTED to cil_events,
       action discarded, authority remains PROPOSED

  Pre-approval writes carry PROPOSED authority.
  AUTO_ENRICHED is only assigned after approval.
  This is not negotiable — see CLAIMS_AND_EVENTS_CANON.md Section 4.

Verification hook:
  Simulate inventory count at 15. Assert "move to inventory" action
  is blocked. Assert HARD_STOP_ENFORCED appears in cil_events.
  Then simulate SOVEREIGN override with reason. Assert action proceeds
  and HARD_STOP_OVERRIDDEN appears in cil_events with reason text.

---

### STEP 3 — Channel Selection Layer

File: backend/membrane/channel_selector.py

Purpose: Receive a CIL significance flag and session context, decide
which channel delivers the notification, and dispatch accordingly.

The channel rules live in the policy registry (Domain CHANNELS).
The channel selector reads them. It does not hardcode them.

Current channel policy:

  cashflow_alert_channel:      SMS_SOVEREIGN_ALWAYS
    CASHFLOW_ALERT events go to SMS regardless of session state.
    Reason: cash flow does not wait for an active session.

  insurance_critical_channel:  SMS_AND_WEBSOCKET
    INSURANCE_EXPOSURE_ALERT at 95% threshold goes to both channels.

  title_deadline_channel:      WEBSOCKET_IF_ACTIVE_ELSE_SMS
    COMPLIANCE_ALERT for Iowa title deadline goes to WebSocket if
    a SOVEREIGN session is active, otherwise SMS.

  anomaly_default_channel:     WEBSOCKET_ONLY
    Standard anomaly alerts go to WebSocket only.

  hard_stop_channel:           WEBSOCKET_BLOCK_WITH_UI_MESSAGE
    HARD_STOP_ENFORCED goes to WebSocket as a blocking UI message.

Channel dispatch functions needed:
  dispatch_sms(user_id, message, event_id)
    - Calls Twilio via existing twilio_webhooks.py
    - Logs OUTBOUND_SMS_SENT to cil_events with correlation_id
      linking back to the triggering event

  dispatch_websocket(session_id, plate_type, payload, event_id)
    - Sends MOUNT_PLATE command to the active WebSocket connection
    - Logs to cil_events as ADVISORY if informational,
      or HARD_STOP_ENFORCED if blocking

  dispatch_both(user_id, session_id, plate_type, payload, event_id)
    - Calls both dispatch functions
    - Both log to cil_events with the same correlation_id

Every dispatch logs to cil_events. No silent dispatches.

Verification hook:
  Simulate a CASHFLOW_ALERT event. Assert SMS is dispatched regardless
  of whether a WebSocket session is active. Assert OUTBOUND_SMS_SENT
  appears in cil_events with correct correlation_id linking back to
  the CASHFLOW_ALERT event.

---

### STEP 4 — Translation Engine

File: backend/membrane/translation_engine.py

Purpose: Convert CIL domain events into UI-appropriate MOUNT_PLATE
payloads. This is the only place where CIL event vocabulary maps to
UI plate vocabulary.

The translation engine is a pure mapping layer. It receives a CIL event,
reads the payload, and returns a MOUNT_PLATE command. It contains no
business logic.

Required translations:

  CIL Event                   → UI Plate
  ─────────────────────────────────────────────────────────────────
  VEHICLE_STATUS_UPDATED      → MOUNT_PLATE: INVENTORY (Digital Twin)
  THRESHOLD_BREACHED          → MOUNT_PLATE: HARD_STOP
  THRESHOLD_APPROACHING       → MOUNT_PLATE: ANOMALY_ALERT
  COMPLIANCE_ALERT            → MOUNT_PLATE: COMPLIANCE (title warning)
  CASHFLOW_ALERT              → MOUNT_PLATE: ANOMALY_ALERT (CIT flag)
  INSURANCE_EXPOSURE_ALERT    → MOUNT_PLATE: ANOMALY_ALERT (exposure meter)
  ENRICHMENT_PROPOSED         → MOUNT_PLATE: APPROVAL_REQUIRED
  CONFLICT_DETECTED           → MOUNT_PLATE: COLLISION_RESOLUTION
  QUESTION_CREATED            → MOUNT_PLATE: OPEN_QUESTION (Task 2.4)
  ENTITY_TRANSFER             → MOUNT_PLATE: INVENTORY (entity handoff)
  HARD_STOP_ENFORCED          → MOUNT_PLATE: HARD_STOP (blocking)

Each MOUNT_PLATE payload must include:
  plate_id:       string identifier for the React component
  data:           structured payload the plate needs to render
  blocking:       bool — true if this plate blocks other UI interaction
  event_id:       the cil_events event_id that triggered this mount
  correlation_id: for tracing this plate back to the original event chain

The five compliance indicators map to specific plate data shapes:

  Title Bottleneck Warning:
    plate_id: "COMPLIANCE_TITLE_BOTTLENECK"
    data: { missing_count, critical_vins: [{vin, days_remaining, entity}] }

  Inventory Count Gauge:
    plate_id: "COMPLIANCE_INVENTORY_GAUGE"
    data: { current_count, max_units, warning_units, entity_breakdown }

  Capital Exposure Tracker:
    plate_id: "COMPLIANCE_EXPOSURE_METER"
    data: { total_exposure, ceiling, pct_used, threshold_80, threshold_90,
            threshold_95, per_entity_breakdown }

  Aged CIT Flag:
    plate_id: "COMPLIANCE_CIT_FLAG"
    data: { aged_deals: [{deal_id, vin, days_since_funding, lender, amount}] }

  Stale Inventory Tile:
    plate_id: "COMPLIANCE_STALE_INVENTORY"
    data: { stale_units: [{vin, days_in_stock, status, entity, last_action}] }

Verification hook:
  Feed a COMPLIANCE_ALERT event with days_remaining=3 into the
  translation engine. Assert output is MOUNT_PLATE with
  plate_id="COMPLIANCE_TITLE_BOTTLENECK" and correct data shape.
  Assert blocking=false (title warning is not a hard stop, it is urgent).

---

### STEP 5 — WebSocket Subscription Router

File: backend/membrane/ws_router.py

Purpose: Own the WebSocket connection lifecycle and route events to the
correct active sessions. This replaces the current chat_stream.py
which is doing this incorrectly inside the CIL layer.

Migration plan:
  1. Build ws_router.py in membrane/
  2. Move WebSocket connection management from chat_stream.py to ws_router.py
  3. chat_stream.py becomes a thin CIL-layer component that only
     handles intent classification and response generation
  4. ws_router.py handles connection registry, session binding,
     and MOUNT_PLATE dispatch

Connection model:
  - One WebSocket connection per active user session
  - Connection is bound to a SessionContext on connect
  - All MOUNT_PLATE events route through ws_router.py
  - ws_router.py checks session_context.entity_scope before
    delivering any event — a FIELD user cannot receive
    SOVEREIGN-scoped plate data

Connection registry:
  active_connections: dict[session_id, WebSocket]

Required methods:
  connect(websocket, session_context)
  disconnect(session_id)
  send_plate(session_id, plate_payload)
  broadcast_to_role(role, plate_payload)  # for system-wide alerts

Verification hook:
  Connect two sessions with different roles (SOVEREIGN and FIELD).
  Emit a SOVEREIGN-scoped COMPLIANCE_ALERT.
  Assert SOVEREIGN session receives the MOUNT_PLATE.
  Assert FIELD session does not receive it.

---

### STEP 6 — Component Splits (after Steps 1-5 are complete)

After the five membrane components exist and are tested, split the
following existing components along CIL/membrane lines.
Do each split as a separate commit.

router_agent.py
  CIL part: intent classification, entity extraction, domain routing
  Membrane part: session context injection into prompt, response
  delivery decision

attention_dispatcher.py
  CIL part: significance evaluation, threshold comparison, event emission
  Membrane part: channel selection call, delivery orchestration

iea_agent.py
  CIL part: required field evaluation, gap detection, question generation
  Membrane part: question routing to correct owner role in session

hitl_service.py
  CIL part: approval state tracking, authority elevation on approval
  Membrane part: approval gate UI delivery, session pending_approvals management

chat_stream.py
  CIL part: intent classification, response generation (keep here)
  Membrane part: WebSocket connection management (migrate to ws_router.py)

twilio_webhooks.py
  CIL part: identity resolution, claim extraction from inbound SMS
  Membrane part: session context lookup, response routing

---

## The DealerCenter and myKaarma Replacement Contracts

These are membrane-level integration points. Build them as isolated
spoke files after the five core membrane components are stable.
Each spoke follows the existing spoke pattern: isolated file, own
policy entries, disable via single flag.

### Spoke 1 — DealerCenter Membrane C Bridge
File: backend/membrane/spokes/dealercenter_spoke.py

This is Membrane C — the compliance bridge. It handles:

1. Scheduled report intake
   DealerCenter emails Active Inventory, Contracts in Transit, and
   Title Status reports daily to the intake address.
   forwarded_detector.py is already ready.
   Wire it to run on schedule and route DealerCenter report emails
   through the standard intake pipeline as documents.
   No special path — they are ExtractedClaims like any other document.

2. Iowa ERT temp tag push (outbound)
   On DEAL_STATE_CHANGED to FUNDED:
   CIL emits event → Membrane C receives it → formats deal data
   for DealerCenter API → pushes for ERT temp tag generation.
   This is an external effect → requires SOVEREIGN approval gate
   before the DealerCenter push executes.

3. FTC vault mirror (outbound)
   On DEAL_STATE_CHANGED to CLOSED:
   Membrane C copies closed deal folder from BigQuery to encrypted
   long-term storage.
   Policy registry entry: ftc_retention_years: 10

Policy registry entries needed for this spoke:
  dealercenter_reports_email:          [intake address]
  dealercenter_ert_approval_required:  true
  ftc_vault_destination:               [encrypted storage path]
  dealercenter_spoke_enabled:          true

### Spoke 2 — Twilio Operational Loops (myKaarma replacement)
File: backend/membrane/spokes/twilio_ops_spoke.py

Three loops. All are external effects. All require approval or
are triggered by explicit human action.

Loop 1 — Automatic Status SMS
  Trigger: VEHICLE_STATUS_UPDATED event where new_status = AVAILABLE
  Membrane receives event, checks if customer contact exists in
  master_person_graph for this VIN's deal record.
  If contact found: emits ENRICHMENT_PROPOSED for SOVEREIGN approval.
  On approval: dispatches Twilio SMS with /quote/:uuid link.
  Logs OUTBOUND_SMS_SENT to cil_events with VIN anchor and correlation_id.
  
  SMS template (read from policy registry, not hardcoded):
  "Hi {name}, your {year} {make} {model} is ready. View report: {quote_url}"

Loop 2 — Proof-of-Damage Video
  Trigger: Staff uploads video via PWA to /api/media/ingest with
  VIN and job_type=WALKAROUND
  This is an intake event, not an outbound dispatch.
  Pipeline: intake → Gemini Veo analysis → digital_twin_flags update
  → WALKAROUND_UPLOADED event emitted
  → Membrane A marks service initiation as unblocked for this VIN
  No approval required (this is an internal write, no external effect).
  
  Required: timestamp and VIN must be present on upload.
  Reject upload if VIN is missing — do not accept VIN_NOT_PROVIDED
  for walkaround uploads. Walkaround without VIN is not defensible.

Loop 3 — SMS Approval to Communication Certificate
  Trigger: Inbound SMS reply "YES" or /quote/:uuid digital approval
  CIL records HumanAssertion: REPAIR_AUTHORIZED, authority: CUSTOMER
  Membrane receives REPAIR_AUTHORIZATION_RECEIVED event
  Membrane triggers PDF generation for Communication Certificate
  PDF attached to service RO in BigQuery under VIN record
  Membrane emits COMMUNICATION_CERTIFICATE_GENERATED to cil_events
  
  PDF must include: VIN, job description, authorized amount, customer
  name, approval timestamp, approval channel (SMS or quote portal),
  Twilio message SID or quote UUID for verification.

Policy registry entries needed for this spoke:
  status_sms_template:                 [template string]
  status_sms_approval_required:        true
  walkaround_vin_required:             true
  communication_cert_auto_generate:    true
  twilio_ops_spoke_enabled:            true

---

## Emit Rules for Membrane Components

Every membrane component that takes an enforcement action must emit
to cil_events. No silent enforcement.

Required emissions by step:

  Session Context Manager:
    SESSION_STARTED, SESSION_ENDED

  Policy Enforcer:
    HARD_STOP_ENFORCED (with blocked_action, policy_key, current_value)
    HARD_STOP_OVERRIDDEN (with reason, actor_id — required)
    ENRICHMENT_APPROVED (with actor_id, action_id)
    ENRICHMENT_REJECTED (with actor_id, action_id, reason if given)

  Channel Selector:
    OUTBOUND_SMS_SENT (every SMS dispatched, with event_id correlation)

  Translation Engine:
    No direct emissions — it is a pure mapping function.

  WebSocket Router:
    No direct emissions — delivery is logged by the component
    that triggered the delivery (channel selector or policy enforcer).

---

## What Antigravity Must NOT Do in Phase 3

- Do not add policy evaluation logic to any membrane component.
  If a membrane component needs to know a threshold, it calls a CIL
  endpoint to get the evaluated result. It does not read the policy
  registry directly and compute the result itself.

- Do not upgrade authority on any fact inside the membrane.
  Authority elevation (PROPOSED → AUTO_ENRICHED) is a CIL operation.
  The membrane approves the action; the CIL elevates the authority.

- Do not write to system_audit_ledger directly from any membrane
  component. Membrane emits to cil_events. The projection pipeline
  handles audit_ledger population.

- Do not store session state in BigQuery. Session context is ephemeral.
  The events are durable. The context object is not.

- Do not build the UI architecture brief yet. That is issued after
  Membrane A is stable. A UI built before the membrane exists will
  couple to the wrong layer.

---

## Handoff Protocol for This Brief

When each step is complete:
1. Commit with descriptive message referencing the step number
   (e.g., "feat: membrane step 1 — session context manager")
2. Push to GitHub main
3. Confirm commit hash
4. Report completion of verification hook

Do not batch multiple steps into one commit.
Do not start the component splits (Step 6) until Steps 1-5 are
complete and all verification hooks pass.

---

## Session Handoff Note

Pilot path (pressure test of extraction pipeline) is pending resolution
of a Replit deployment issue. The four extraction fixes exist in local
Cursor but were not pushed to GitHub before this brief was issued.

Antigravity should push those four fixes in a separate commit BEFORE
starting Phase 3 membrane work. The commit message for the extraction
fixes is documented in this session.

Two parallel tracks once extraction fixes are pushed:
  Track A (Antigravity): Phase 3 membrane build per this brief
  Track B (Moaz + Replit): pilot path execution with Test.pdf

They do not block each other. Membrane build is backend/membrane/.
Pilot path operates on existing backend/pipeline/ code.

---

AutoHaus · Carbon LLC · C-OS v3.1.1-Alpha
PHASE3_MEMBRANE_BUILD_BRIEF.md v1.0
Issued March 2, 2026
ENDDOC