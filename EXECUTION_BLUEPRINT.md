# AUTOHAUS C-OS: EXECUTION BLUEPRINT
**Machine-Readable Roadmap for the Conversational Operating System (v3.1)**

> **AI INSTRUCTION:** You are resuming the build of the AutoHaus Central Intelligence Layer. Before executing any module below, you MUST read `AUTOHAUS_SYSTEM_STATE.json` to acquire the active operational context, backend definitions, and design constraints.

---

## # MODULE 1: Module_Identity_Bedrock
- **Goal:** Finalize the Human Graph by linking incoming communication payloads to probabilistic Identity Engine merges.
- **Pre-requisites:** `identity_resolution.py` must exist and `master_person_graph` BigQuery table must be active. (Verify in `AUTOHAUS_SYSTEM_STATE.json`).
- **Technical Specs:** 
  1. Create a FastAPI endpoint `POST /api/crm/intake`.
  2. Accept JSON: `{ "source": "WEB_LEAD", "email": "...", "phone": "..." }`.
  3. Call `IdentityEngine.resolve_identity()`.
  4. Return the universal `master_person_id` and `confidence_score`.
- **State Update:** Append `"crm_intake_api": "active"` to `backend_primitives` in `AUTOHAUS_SYSTEM_STATE.json`.
- **Verification Hook:** Send a test cURL hitting the endpoint with a known email and verify it returns a 200 OK with the existing `master_person_id`.

---

## # MODULE 2: Module_Agentic_Router (The Concept Orchestrator)
- **Goal:** The core "Brain" of the Chief of Staff. Routes human natural language to the correct backend agent/logic.
- **Pre-requisites:** The Gemini API key must be hydrated in the `.env`.
- **Technical Specs:**
  1. Create `10_IT_AI_Core_Layer/backend/agents/router_agent.py`.
  2. Implement an LLM call using `google-generativeai` (Gemini 1.5 Pro).
  3. The prompt must strictly classify intent into specific domains: `[FINANCE, INVENTORY, SERVICE, CRM]`.
  4. Return a structured JSON response identifying the intent and extracted entities (e.g., `{"intent": "FINANCE", "entities": {"lane": "A"}}`).
- **State Update:** Append `"agentic_router": "active"` to `backend_primitives` in `AUTOHAUS_SYSTEM_STATE.json`.
- **Verification Hook:** Execute a Python test script passing "Show me the financials for Lane A" and assert that the output JSON strictly matches the `FINANCE` intent.

---

## # MODULE 3: Module_JIT_Plate_Protocol
- **Goal:** The WebSocket/Handshake logic enabling the Python CIL to push dynamic React UI components ("Plates") to the frontend.
- **Pre-requisites:** `Module_Agentic_Router` must be active. A React frontend (Hub) must be listening.
- **Technical Specs:**
  1. Create `10_IT_AI_Core_Layer/backend/routes/chat_stream.py`.
  2. Implement a WebSocket endpoint (`/ws/chat`).
  3. When the router classifies an intent (e.g., `FINANCE`), the WebSocket must emit a specific JSON payload tailored for React: `{"type": "MOUNT_PLATE", "plate_id": "FINANCE_CHART", "dataset": [...]}`.
- **State Update:** Append `"jit_websocket": "active"` to `backend_primitives`.
- **Verification Hook:** Run a WebSockets test client (e.g., `wscat`), send a dummy command, and verify a `"MOUNT_PLATE"` event is streamed back.

---

## # MODULE 4: Module_Sovereign_Memory
- **Goal:** Implement Vertex AI Vector Search to give the CEO a long-term Memory Vault distinct from operational SQL data.
- **Pre-requisites:** GCP Project must have Vertex AI API enabled.
- **Technical Specs:**
  1. Create `10_IT_AI_Core_Layer/backend/memory/vector_vault.py`.
  2. Implement logic using Gemini Text Embeddings (`text-embedding-004`).
  3. Create an upsert function: `store_preference(user_id, "Ahsin prefers margin reports grouped by week")`.
  4. Create a recall function: `get_context(query_string)`. This returns the top K similar memory strings to inject into the Chatbot's system prompt before generating a reply.
- **State Update:** Append `"sovereign_memory_vector_db": "active"` to `backend_primitives`.
- **Verification Hook:** Store a dummy preference, recall it using a semantically similar (but not exact) string, and assert the preference is returned as the top match.

---

## # MODULE 5: Module_Anomaly_Monitor (The Sleep Monitor)
- **Goal:** The asynchronous worker for proactive discovery, acting as the autonomous 24/7 auditor.
- **Pre-requisites:** `system_audit_ledger` BigQuery table must be populated.
- **Technical Specs:**
  1. Create `10_IT_AI_Core_Layer/scripts/anomaly_engine.py`.
  2. Write a BigQuery SQL script that flags anomalies (e.g., transport costs > 2 standard deviations from the 30-day mean).
  3. If an anomaly is found, execute a Twilio API call to push an SMS alert to the CEO's configured mobile number.
- **State Update:** Append `"anomaly_monitor": "active"` to `backend_primitives`.
- **Verification Hook:** Insert a fake $5,000 transport fee into the BigQuery ledger, run `anomaly_engine.py`, and verify the script triggers the Twilio dispatch function.

---

## # MODULE 6: Module_Omnichannel_Ear (Twilio Sync)
- **Goal:** Replicate MyKaarma's "Single Local Number" feature natively via the CIL and Identity Engine.
- **Pre-requisites:** `Module_Identity_Bedrock` active. Twilio Account SID/Token in `.env`.
- **Technical Specs:**
  1. Create `10_IT_AI_Core_Layer/backend/routes/twilio_webhooks.py`.
  2. Implement `POST /api/webhooks/twilio/sms` to receive inbound SMS.
  3. Extract the sender's phone number, query the `IdentityEngine` to find their `master_person_id`.
  4. Query the `inventory_master` to find their open Repair Order/Deal and route the message via Slack/SMS to the specifically assigned AutoHaus staff member.
- **State Update:** Append `"omnichannel_twilio": "active"` to `backend_primitives`.
- **Verification Hook:** Send a text to the Twilio number and verify the console logs a payload matching the phone number to an existing `master_person_id`.

---

## # MODULE 7: Module_Client_JIT_Portal (Digital Quotes)
- **Goal:** Oust MyKaarma's quote approval UI by allowing the CIL to text a dynamic "Approval Plate" directly to customers.
- **Pre-requisites:** `Module_JIT_Plate_Protocol` active.
- **Technical Specs:**
  1. Create a public-facing React route in the Replit frontend: `/quote/:uuid`.
  2. Create a backend endpoint `GET /api/public/quote/{uuid}` that pulls the specific Digital Twin flag (e.g., "Rusty Subframe") and the associated repair cost.
  3. Build a React component (`ApprovalPlate.jsx`) that renders the Red/Yellow/Green defect report with a "Digitally Sign & Approve" button.
- **State Update:** Append `"customer_jit_quotes": "active"` to `backend_primitives`.
- **Verification Hook:** Hardcode a test UUID in BigQuery, navigate to the React route, and verify the quote renders and the "Approve" button triggers a backend success log.

---

## # MODULE 8: Module_Logistics_Tracking (P&D Driver Maps)
- **Goal:** Provide Uber-style live tracking links for Fluiditruck and Carlux customers.
- **Pre-requisites:** Google Maps API key active.
- **Technical Specs:**
  1. Establish a lightweight Google AppSheet connected to BigQuery.
  2. Create `10_IT_AI_Core_Layer/backend/routes/logistics.py` with `POST /api/logistics/location`.
  3. When an AppSheet driver starts a route, send a Twilio SMS to the customer containing a unique React frontend link (e.g., `/track/:uuid`) mapping the driver's coordinates.
- **State Update:** Append `"logistics_tracking": "active"` to `backend_primitives`.
- **Verification Hook:** Push mock coordinates to the logistics API, open the tracking URL, and verify the UI plots the location on a Google Map component.

---

## # MODULE 9: Module_Intelligent_Membrane
- **Goal:** Build the Bidirectional AI Middleware to catch messy human inputs (Routing/CSM) and translate CIL outputs (Attention Model).
- **Pre-requisites:** `Module_Identity_Bedrock` and `Module_Agentic_Router` active.
- **Technical Specs:**
  1. Create `10_IT_AI_Core_Layer/backend/memory/csm.py` (Conversation State Manager) using SQLite for active session persistence.
  2. Implement `IEA` (Input Enrichment Agent) in `agents/iea_agent.py` upgrading the Router to handle "Incomplete" prompts and dispatching questions via CSM.
  3. Create `agents/attention_dispatcher.py` to route events based on urgency (SMS vs WebSocket).
- **State Update:** Append `"intelligent_membrane": "active"` to `backend_primitives`.
- **Verification Hook:** Send an incomplete text message, verify CSM enters `PENDING` state and Twilio sends a clarifying question back. Reply to text, and verify CSM resumes original intent.

---

## # MODULE 10: Module_Telemetry_And_Observability
- **Goal:** Provide measurable analytics on C-OS performance, error rates, and lead conversion times.
- **Pre-requisites:** Central SQLite DB or BigQuery connection active.
- **Technical Specs:**
  1. Capture all WebSocket `MOUNT_PLATE` events and log them into `system_audit_ledger` (with latency and intent metadata).
  2. Measure execution time across the IEA $\rightarrow$ Router $\rightarrow$ Attention Dispatcher chain.
  3. Create a specialized JIT Plate (`SYSTEM_HEALTH_DASHBOARD`) capable of rendering error rates and average response times visually.
- **State Update:** Append `"telemetry_observability": "active"` to `backend_primitives`.
- **Verification Hook:** Use the Chatbot to ask "What is our error rate today?" — verify that the `SYSTEM_HEALTH_DASHBOARD` plate is hydrated over WebSocket.

---

## # MODULE 11: Module_Visual_Scribe (Phase 2 Enhancement)
- **Goal:** Gemini Veo analysis of mechanic walk-around videos to extract and write structured defect data to BigQuery Digital Twins.
- **Pre-requisites:** Google Cloud Storage bucket mapped; Gemini multimodel APIs enabled; Digital Twin schema adjusted in `inventory_master`.
- **Technical Specs:**
  1. Video ingestion via `POST /api/media/ingest` from mechanic devices (AppSheet or mobile interface).
  2. Backend delegates to Gemini 1.5 Pro with prompt to extract mechanical defects and spatial assignments.
  3. Emit structured updates into `digital_twin_flags` within BigQuery `inventory_master`.
- **State Update:** Append `"visual_scribe_engine": "planned"` to `backend_primitives`.
- **Verification Hook:** Upload a 30s video complaining about "metal on metal rotors," verify a BigQuery `UPDATE` logs a severity warning to the appropriate VIN's twin record.
