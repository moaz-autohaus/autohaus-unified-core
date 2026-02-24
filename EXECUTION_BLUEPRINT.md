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
