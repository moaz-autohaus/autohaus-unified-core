# AUTOHAUS C-OS: COMMUNICATION PROTOCOL (v3.1)
**The Technical Handshake between Chatbot, CIL, and UI Plates**

To graduate from an "AI Intake Engine" to a fully "Conversational Operating System," we must wire the transmission between the Human Intent (Chatbot), the Brain (CIL), and the Display (UI). This document defines the four critical handshake protocols required to resolve process gaps.

---

## 1. The "Ambiguity Resolution" Protocol (Collision Detection)
*The Problem:* The user says "Update the M4," but the CIL detects two M4s in the Inventory Master (one in KAMM, one in Fluiditruck).
*The Solution:* The CIL pauses execution and asks the UI to hydrate a **Selection Plate**.

**Technical Flow:**
1.  **Intent Classification:** Chatbot routes intent to `Inventory_Agent`.
2.  **SQL Collision:** CIL queries BigQuery for "BMW M4" and returns 2 rows.
3.  **WebSocket Pulse:** CIL emits a `REQUIRED_ACTION` payload to the UI:
    ```json
    {
      "pulse_type": "AMBIGUITY_RESOLUTION",
      "chatbot_message": "I found two BMW M4s. Which one?",
      "plate_id": "RESOLVE_ENTITY_PLATE",
      "payload": [ 
         {"vin": "WBA123", "entity": "KAMM_LLC"}, 
         {"vin": "WBA999", "entity": "FLUIDITRUCK_LLC"} 
      ]
    }
    ```
4.  **UI Mount:** React hides the generic dashboard and instantly mounts a dual-card UI Plate. The CEO taps the KAMM M4.
5.  **Resolution:** The UI sends `{"selected_vin": "WBA123"}` back via WebSocket, and the Chatbot resumes the original workflow.

---

## 2. Cross-Entity "Hand-Off" Chain (The Billable Trigger)
*The Problem:* A vehicle moves from AutoHaus Services (Lane A) to AstroLogistics (Lane B). MSO rules dictate strict insurance segregation. Carbon LLC carries no risk.
*The Solution:* The CIL intercepts the status change and automatically generates intercompany billing.

**Technical Flow:**
1.  **State Change:** Mechanic in Lane A marks job "Green Tag" (Complete).
2.  **CIL Intercept:** FastApi route `/api/service/update_status` receives the change.
3.  **Billable Trigger Logic:** The CIL reads `business_ontology.json`. It sees the VIN is moving from `AUTOHAUS_SERVICES_LLC` to `ASTROLOGISTICS_LLC`.
4.  **Automated FinOps:** The CIL automatically generates a Draft Invoice for the mechanical labor, attributing Accounts Receivable to Services and Accounts Payable to AstroLogistics. 
5.  **Audit Log:** The transition is immutably stamped in `system_audit_ledger` with the associated insurance policy bounds (e.g., *Risk successfully transferred from Garagekeepers to Bailee Coverage*).

---

## 3. The "Visual Scribe" Feedback Loop (Entity-Attribute Linker)
*The Problem:* The AI Scribe transcribes a mechanic saying, "I see rust on the subframe." This data sits useless in a raw text log.
*The Solution:* The CIL maps free-form text directly to the BigQuery Digital Twin schema.

**Technical Flow:**
1.  **Media Intake:** Mechanic records a 30-second walk-around video. App uploads it to `/api/media/ingest`.
2.  **Gemini Veo Analysis:** CIL passes video and audio to Gemini 1.5 Pro.
3.  **Attribute Extraction Prompt:** *"Extract mechanical defects and map them to physical vehicle zones."*
4.  **Digital Twin Update:** CIL issues a SQL `UPDATE` to the `inventory_master` table, appending a JSON object to the `digital_twin_flags` column:
    ```json
    {
      "zone": "Subframe",
      "issue": "Rust Modification",
      "severity": "YELLOW",
      "source": "Mechanic Audio Transcript"
    }
    ```
5.  **Sales UI Hydration:** When a Sales Agent later pulls up the vehicle's JIT Plate, the UI reads the `YELLOW` flag and displays a warning directly on the 3D model.

---

## 4. JIT "Plate Hydration" Logic (FastAPI-to-React WebSocket)
*The Problem:* Traditional standard HTTP requests require the user to refresh the page to see new data. The C-OS must feel "Liquid" and instant.
*The Solution:* The entire UI is driven by an asynchronous WebSocket event emitter.

**Technical Flow:**
1.  **WebSocket Connection:** When the Replit UI starts, it opens a persistent `wss://` connection to the Python backend.
2.  **The Event Loop:** The Chatbot constantly evaluates state.
3.  **The Pulse Emitter:** Instead of the UI asking for data, the CIL *pushes* data.
    ```python
    async def push_plate(client_id, plate_type, data):
        message = {
            "action": "MOUNT_PLATE",
            "component": plate_type,
            "data": data
        }
        await websocket_manager.send_personal_message(message, client_id)
    ```
4.  **React Rendering:** The React root component contains a `<PlateHydrator />`. It listens for `MOUNT_PLATE`. If it receives `component: "FINANCE_CHART"`, it dynamically imports the Recharts component and renders the JSON data directly into the chat stream without a single page reload.

---

## 5. Fallback & Error Recovery Protocol
*The Problem:* Networks drop, APIs rate-limit, and databases timeout. A resilient C-OS cannot silently fail.
*The Solution:* Predictable degradation paths for every critical handshake.

**Technical Flow & Failovers:**
1.  **WebSocket Dropped:** If the frontend loses connection, the React UI stores inputs in a `localStorage` outbox and enters a "Reconnecting..." ghost state. Upon reconnect, it flushes the outbox to the backend.
2.  **LLM / Gemini Outage:** If the `google.generativeai` API returns a 429 or 503, the Agentic Router triggers the **Model Failover Chain** (Flash -> Pro -> Local Keyword Rules). If all fail, it returns an explicit `UNKNOWN` intent with `urgency_score: 8` and an error plate, ensuring the CEO explicitly sees the API failure, rather than the system freezing.
3.  **BigQuery Unreachable:** (e.g., missing Service Account keys). The Identity Engine and Router catch the exception and immediately push a `SYSTEM_ERROR` plate to the active WebSocket. Operations requiring state changes are appended to a SQLite `dead_letter_queue` for later reconciliation.
