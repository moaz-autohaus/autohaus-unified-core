# AutoHaus Unified Core — Pipeline Diagnostic Audit

This document provides a comprehensive, sequential mapping of every operation within the AutoHaus Central Intelligence Layer (CIL) and Unified Command Center (UCC).

## 1. Backend API & Routing (FastAPI)

- **`main.py / lifespan`**
  - **Inputs:** FastAPI startup/shutdown events.
  - **Action:** Initializes the system lifecycle, inclusive of legal route registration and background worker readiness.
  - **Outputs:** Operational service health.
  - **Calls next:** `legal_router`, `StaticFiles`.
  - **Decision:** No.
  - **Operation Type:** STRUCTURAL
  - **Commitment Level:** NON-COMMITTING
  - **Durability of Output:** EPHEMERAL
  - **Context Window:** Application startup parameters
  - **Fork Governed:** None.
  - **Propagation Check:** Initializes app state.

- **`identity_routes.py / process_crm_intake`**
  - **Inputs:** `LeadIntakeRequest` (Source, optional Email/Phone/Name).
  - **Action:** Traces inbound leads through the probabilistic Identity Engine to resolve against the Human Graph.
  - **Outputs:** Universal Master Person ID and confidence score.
  - **Calls next:** `IdentityEngine.resolve_identity`, `trigger_membrane_attention` (Background).
  - **Decision:** Yes (rejects if contact info is missing).
  - **Operation Type:** PROBABILISTIC
  - **Commitment Level:** COMMITTING
  - **Durability of Output:** DURABLE_CONCLUSION
  - **Context Window:** Request payload + BigQuery `master_person_graph`
  - **Fork Governed:** Identity match triggers branch to create new vs update existing Master Person ID.
  - **Propagation Check:** Writes to `master_person_graph` and fires membrane attention.

- **`identity_routes.py / trigger_membrane_attention`**
  - **Inputs:** Lead request and resolved identity result.
  - **Action:** Evaluates a lead event for executive urgency and broadcasts a JIT CRM Plate to the UI.
  - **Outputs:** WebSocket event (`MOUNT_PLATE`).
  - **Calls next:** `AttentionDispatcher.evaluate_event`, `manager.broadcast`.
  - **Decision:** No.
  - **Operation Type:** INTELLIGENT
  - **Commitment Level:** NON-COMMITTING
  - **Durability of Output:** EPHEMERAL
  - **Context Window:** Merged lead information + Entity tag
  - **Fork Governed:** Evaluates urgency to build `MOUNT_PLATE` payload and WS updates.
  - **Propagation Check:** Pushed to UI via WebSocket manager broadcast.

- **`pipeline_routes.py / trigger_ingest`**
  - **Inputs:** `IngestRequest` (Drive File ID, Name).
  - **Action:** Manually injects a document into the extraction and classification pipeline.
  - **Outputs:** Job ID.
  - **Calls next:** `pipeline.queue_worker.enqueue_file`.
  - **Decision:** Yes (validates Drive service status).
  - **Operation Type:** STRUCTURAL
  - **Commitment Level:** COMMITTING
  - **Durability of Output:** LOGGED
  - **Context Window:** Ingest request file metadata
  - **Fork Governed:** None.
  - **Propagation Check:** Pushes job onto worker queue.

- **`intel_routes.py / trigger_gmail_scan`**
  - **Inputs:** Account name (optional), Batch limit.
  - **Action:** Initiates an asynchronous forensic scan of executive Gmail accounts for operational intelligence.
  - **Outputs:** Accepted status.
  - **Calls next:** `gmail_intel.scan_account_full` (Background).
  - **Decision:** No.
  - **Operation Type:** STRUCTURAL
  - **Commitment Level:** NON-COMMITTING
  - **Durability of Output:** EPHEMERAL
  - **Context Window:** Request parameters
  - **Fork Governed:** Forks path based on explicit single account focus vs. full loop.
  - **Propagation Check:** Yields immediate success mapping work to background tasks.

- **`logistics.py / update_location`**
  - **Inputs:** `LocationUpdate` (GPS coords, Driver ID, Status).
  - **Action:** Records a real-time transport trace and triggers customer notifications for en-route drivers.
  - **Outputs:** Success status.
  - **Calls next:** `dispatch_tracking_sms`, BigQuery.
  - **Decision:** Yes (branches on `EN_ROUTE` status).
  - **BigQuery Pattern:** `INSERT INTO autohaus-infrastructure.autohaus_cil.system_audit_ledger (...) VALUES (...)`.
  - **Operation Type:** STRUCTURAL
  - **Commitment Level:** COMMITTING
  - **Durability of Output:** LOGGED
  - **Context Window:** Driver coordinate payload
  - **Fork Governed:** Forks background SMS dispatch based on `EN_ROUTE` status.
  - **Propagation Check:** Writes to `system_audit_ledger` and triggers Twilio.

- **`media_routes.py / ingest_media`**
  - **Inputs:** File upload, Actor ID.
  - **Action:** Captures uploaded documents, performs initial mock extraction, and stages a HITL proposal.
  - **Outputs:** Proposal ID and status.
  - **Calls next:** `hitl_service.propose`.
  - **Decision:** Yes (validates eligibility for ingestion).
  - **Operation Type:** INTELLIGENT
  - **Commitment Level:** COMMITTING
  - **Durability of Output:** DURABLE_CONCLUSION (Stages HITL Proposal)
  - **Context Window:** Uploaded file block
  - **Fork Governed:** Rejects early if HITL rules block ingestion.
  - **Propagation Check:** Prepares action schema and writes Proposal to BQ `hitl_events`.

- **`anomalies.py / get_active_anomalies`**
  - **Inputs:** BigQuery client.
  - **Action:** Retrieves unresolved data drift and fiscal anomalies from background sweep tables.
  - **Outputs:** List of anomaly objects.
  - **Calls next:** BigQuery.
  - **Decision:** No.
  - **BigQuery Pattern:** `SELECT * FROM autohaus_cil.drift_sweep_results WHERE resolved = FALSE LIMIT 50`.
  - **Operation Type:** STRUCTURAL
  - **Commitment Level:** NON-COMMITTING
  - **Durability of Output:** EPHEMERAL
  - **Context Window:** BigQuery state
  - **Fork Governed:** None.
  - **Propagation Check:** Resolves query directly to client connection.


- **`inventory.py / promote_vehicle`**
  - **Inputs:** Vehicle ID, Actor ID.
  - **Action:** Executes a two-phase commit to move a vehicle to LIVE status and log it to the audit ledger.
  - **Outputs:** Success status and transaction ID.
  - **Calls next:** BigQuery.
  - **Decision:** Yes (aborts if already LIVE).
  - **BigQuery Pattern 1:** `UPDATE autohaus_cil.inventory_master SET status = 'Live' WHERE id = @v_id AND status = 'Pending'`.
  - **BigQuery Pattern 2:** `INSERT INTO autohaus-infrastructure.autohaus_cil.system_audit_ledger (...) VALUES (...)`.
  - **Operation Type:** STRUCTURAL
  - **Commitment Level:** COMMITTING
  - **Durability of Output:** DURABLE_CONCLUSION
  - **Context Window:** Current row context for payload logic
  - **Fork Governed:** Short circuits if no rows updated.
  - **Propagation Check:** Alters global `inventory_master` and issues ledger confirmation in `system_audit_ledger`.

- **`security_access.py / verify_security_access`**
  - **Inputs:** Bearer token.
  - **Action:** Authenticates egress requests against a bcrypt hash in the environment.
  - **Outputs:** Boolean or 404.
  - **Calls next:** None.
  - **Decision:** Yes.
  - **Operation Type:** STRUCTURAL
  - **Commitment Level:** NON-COMMITTING
  - **Durability of Output:** EPHEMERAL
  - **Context Window:** Environment variable hash vs extracted request cookie/bearer.
  - **Fork Governed:** Halts HTTP context via 401 response on mismatch.
  - **Propagation Check:** Passes flow context transparently to secure endpoint mappings.

## 2. Agentic Layer (Neural Processing)

- **`router_agent.py / classify`**
  - **Inputs:** Raw text command.
  - **Action:** Maps human language to operational domains (Finance, Inventory, etc.) and extracts entities.
  - **Outputs:** `RoutedIntent` object.
  - **Calls next:** Gemini API.
  - **Decision:** Yes (model failure switch).
  - **Gemini Call:** `gemini-2.5-flash` (Primary) / `gemini-2.5-pro` (Fallback).
  - **Prompt Template:** `ROUTER_SYSTEM_PROMPT` (contains entity rules for LLCs).
  - **Response Use:** Intent classification and entity extraction for UI routing.
  - **Operation Type:** INTELLIGENT
  - **Commitment Level:** NON-COMMITTING
  - **Durability of Output:** EPHEMERAL
  - **Context Window:** Raw text command
  - **Fork Governed:** Routes query to specific domain logic and UI plate.
  - **Propagation Check:** Returned to caller, used to build UI payload.

- **`iea_agent.py / evaluate`**
  - **Inputs:** Text message, Conversation context.
  - **Action:** Analyzes message completeness (The Intelligent Membrane) before routing.
  - **Outputs:** `IEA_Result` (COMPLETE / INCOMPLETE).
  - **Calls next:** Gemini API.
  - **Decision:** Yes (triggers clarifying question if incomplete).
  - **Gemini Call:** `gemini-2.5-flash`.
  - **Prompt Template:** `IEA_SYSTEM_PROMPT` (instructs to identify missing VINs or ROs).
  - **Response Use:** Pipeline flow control (Pass/Fail).
  - **Operation Type:** INTELLIGENT
  - **Commitment Level:** NON-COMMITTING
  - **Durability of Output:** EPHEMERAL
  - **Context Window:** Current message + conversation history context
  - **Fork Governed:** Bypasses routing to ask clarifying question if incomplete.
  - **Propagation Check:** Returned to chat stream router.

- **`attention_dispatcher.py / evaluate_event`**
  - **Inputs:** Event description.
  - **Action:** Rates operational urgency (1-10) and selects the delivery channel.
  - **Outputs:** `AttentionResult` (Status, Route, Message).
  - **Calls next:** Gemini API.
  - **Decision:** Yes (chooses SMS for scores >= 7).
  - **Gemini Call:** `gemini-2.5-flash`.
  - **Prompt Template:** `ATTENTION_SYSTEM_PROMPT` (contains scale for routine vs. critical).
  - **Response Use:** Channel selection and message synthesis.
  - **Operation Type:** INTELLIGENT
  - **Commitment Level:** NON-COMMITTING
  - **Durability of Output:** EPHEMERAL
  - **Context Window:** Raw event description
  - **Fork Governed:** Determines delivery channel (SMS vs WEBSOCKET) based on urgency score.
  - **Propagation Check:** Results used immediately in websocket push payload.

- **`governance_agent.py / evaluate_governance_command`**
  - **Inputs:** User input, Actor metadata.
  - **Action:** Oversees policy changes, question resolutions, and manual HITL approvals.
  - **Outputs:** Message and Plate ID.
  - **Calls next:** BigQuery, `hitl_service.propose`.
  - **Decision:** Yes (branches on operation type: `POLICY_CHANGE`, `RESOLVE`, etc.).
  - **BigQuery Pattern:** `SELECT * FROM autohaus_cil.open_questions WHERE question_id = @qid`.
  - **Operation Type:** INTELLIGENT
  - **Commitment Level:** COMMITTING (Generates proposals/applies changes)
  - **Durability of Output:** DURABLE_CONCLUSION (Via HITL proposals/applications)
  - **Context Window:** User input + BigQuery ledger (policies, open questions, HITL events)
  - **Fork Governed:** Executes specific governance action based on intent (e.g., policy update vs. status check).
  - **Propagation Check:** Intent parsed, action triggered via HITL service, state updated in BigQuery.

## 3. Persistent Memory & State Management

- **`vector_vault.py / recall`**
  - **Inputs:** Search query.
  - **Action:** Retrieves semantically similar strategic preferences from the Sovereign Memory.
  - **Outputs:** List of `RecallResult` objects.
  - **Calls next:** Gemini API (`embed_content`).
  - **Decision:** No.
  - **Gemini Call:** `models/text-embedding-004`.
  - **Response Use:** Semantic similarity search.
  - **Operation Type:** PROBABILISTIC
  - **Commitment Level:** NON-COMMITTING
  - **Durability of Output:** EPHEMERAL
  - **Context Window:** Query string
  - **Fork Governed:** None.
  - **Propagation Check:** Returns similar memories for upstream context injection.

- **`csm.py / set_state`**
  - **Inputs:** User context and collected entities.
  - **Action:** Persists incomplete interactions to a local SQLite 'Waiting Room'.
  - **Outputs:** Database record.
  - **Calls next:** SQLite.
  - **Decision:** No.
  - **Operation Type:** STRUCTURAL
  - **Commitment Level:** COMMITTING (Local state)
  - **Durability of Output:** LOGGED
  - **Context Window:** Current session state
  - **Fork Governed:** None.
  - **Propagation Check:** Saved locally for session retrieval.

## 4. Operational Services & Spoke Integrations

- **`gmail_intel.py / _process_message`**
  - **Inputs:** Gmail message metadata.
  - **Action:** Ingests email data, extracts operational metrics, and stages state-changes.
  - **Outputs:** BigQuery record and HITL proposals.
  - **Calls next:** BigQuery, `hitl_service.propose`, Gemini.
  - **Decision:** No.
  - **BigQuery Pattern:** `INSERT INTO autohaus_cil.gmail_scan_results (...) VALUES (...)`.
  - **Gemini Call:** `gemini-1.5-flash`.
  - **Prompt Template:** `Extract data from this email... Identify: VINS, Dollar Amounts...`.
  - **Operation Type:** INTELLIGENT
  - **Commitment Level:** COMMITTING
  - **Durability of Output:** DURABLE_CONCLUSION
  - **Context Window:** Email content
  - **Fork Governed:** Extracts entities and optionally proposes state changes via HITL.
  - **Propagation Check:** Data logged to BigQuery `gmail_scan_results`; actionable changes staged as HITL proposals.

- **`attachment_processor.py / _extract_tier0_metrics`**
  - **Inputs:** Raw PDF bytes.
  - **Action:** Performs multimodal OCR to pull high-fidelity financials and VINs from document attachments.
  - **Outputs:** Extracted JSON schema.
  - **Calls next:** Gemini Multimodal.
  - **Decision:** No.
  - **Gemini Call:** `gemini-2.5-flash`.
  - **Prompt Template:** `Analyze this document (attached PDF)... Identify: Purchase Price, Transport Cost...`.
  - **Operation Type:** INTELLIGENT
  - **Commitment Level:** NON-COMMITTING
  - **Durability of Output:** EPHEMERAL
  - **Context Window:** PDF Document image data
  - **Fork Governed:** None.
  - **Propagation Check:** Returns structured JSON for use by caller.

- **`hitl_service.py / validate`**
  - **Inputs:** Proposal ID.
  - **Action:** Checks a proposed change against permissions, scope, and compliance locks.
  - **Outputs:** `VALIDATED` or `REJECTED` status.
  - **Calls next:** BigQuery, `hitl_service.apply` (on success).
  - **Decision:** Yes (auto-applies if low risk).
  - **Operation Type:** STRUCTURAL
  - **Commitment Level:** COMMITTING
  - **Durability of Output:** DURABLE_CONCLUSION
  - **Context Window:** Proposal data from BigQuery + Policy Engine + Security state.
  - **Fork Governed:** Determines if a proposal moves to APPLIED or is REJECTED.
  - **Propagation Check:** Computes delta payload and updates status in `hitl_events`.

- **`hitl_service.py / apply`**
  - **Inputs:** Proposal ID.
  - **Action:** Commits a validated change to core tables and emits a permanent audit log.
  - **Outputs:** Applied status and delta.
  - **Calls next:** BigQuery.
  - **Decision:** Yes (blocks if SYSTEM is FROZEN).
  - **BigQuery Pattern:** `INSERT INTO autohaus_cil.cil_events (...) VALUES (...)`.
  - **Operation Type:** STRUCTURAL
  - **Commitment Level:** COMMITTING
  - **Durability of Output:** DURABLE_CONCLUSION
  - **Context Window:** Validated proposal delta data.
  - **Fork Governed:** Executes the final mutation on target tables (e.g., updating Inventory).
  - **Propagation Check:** Target database tables are permanently updated; event is written to the immutable `cil_events` ledger.

## 5. Unified Command Center (React Frontend)

- **`OrchestratorContext.tsx / WS.onmessage`**
  - **Inputs:** WebSocket event payload.
  - **Action:** Responds to backend commands to mount plates or update terminal chat history.
  - **Outputs:** UI state mutation (`plate`, `messages`).
  - **Calls next:** None.
  - **Decision:** Yes (branches on `data.type`).
  - **WS Event Type:** `MOUNT_PLATE`, `greeting`.
  - **Operation Type:** STRUCTURAL
  - **Commitment Level:** NON-COMMITTING
  - **Durability of Output:** EPHEMERAL
  - **Context Window:** Incoming WS payload
  - **Fork Governed:** Mutates local React state.
  - **Propagation Check:** Triggers React re-render locally.

- **`OrchestratorContext.tsx / sendMessage`**
  - **Inputs:** Chat text, Staged files.
  - **Action:** Dispatches commands to the backend and triggers local predictive responses.
  - **Outputs:** Outgoing WebSocket event, optimistic UI update.
  - **Calls next:** WebSocket.
  - **Decision:** Yes (differentiates file-based vs. text logic).
  - **WS Event Type:** `chat`.
  - **Operation Type:** STRUCTURAL
  - **Commitment Level:** NON-COMMITTING
  - **Durability of Output:** EPHEMERAL
  - **Context Window:** User UI interaction + frontend state
  - **Fork Governed:** Routes to backend or fakes interaction delay for UI preview.
  - **Propagation Check:** Payload transmitted to backend router.

- **`plates.tsx / FinancePlate`**
  - **Inputs:** Financial aggregated data.
  - **Action:** Renders an interactive multi-entity chart of weekly P&L status.
  - **Outputs:** Rendered SVG visualization.
  - **Calls next:** `AreaChart` (Recharts).
  - **Decision:** Yes (filters by entity).
  - **Operation Type:** STRUCTURAL
  - **Commitment Level:** NON-COMMITTING
  - **Durability of Output:** EPHEMERAL
  - **Context Window:** Prop data
  - **Fork Governed:** Toggles chart visibility by entity.
  - **Propagation Check:** Renders inside React tree.

- **`plates.tsx / AnomalyPlate`**
  - **Inputs:** Anomaly event details (e.g. transport cost spike).
  - **Action:** Presents executive controls for approving or overriding system alerts.
  - **Outputs:** Decision event.
  - **Calls next:** Context callback (`onDecision`).
  - **Decision:** Yes.
  - **Operation Type:** STRUCTURAL
  - **Commitment Level:** NON-COMMITTING
  - **Durability of Output:** EPHEMERAL
  - **Context Window:** Prop data
  - **Fork Governed:** Emits APPROVED or OVERRIDE.
  - **Propagation Check:** Selected response passed back up to context handlers.

## 6. Asynchronous Operations

* **Google Drive Ambient Ear**: Polls Drive for new files in `00_Inbox` and routes them through the full neural stack.
* **Logistics tracking**: Webhook updates from AppSheet are logged to BigQuery ledger independently of the user session.
* **Email Forensic Scan**: Batch processing of executive inboxes happens in the background, populating `gmail_scan_results` and staging metadata for HITL.
* **HITL Apply Chain**: Low-risk changes (like metadata adds) are automatically applied to BigQuery without manual intervention, following successful validation.
* **Identity Conflict Resolution**: CRM leads are asynchronously evaluated for Urgency, triggering push notifications via Twilio SMS if classified as high-priority.
