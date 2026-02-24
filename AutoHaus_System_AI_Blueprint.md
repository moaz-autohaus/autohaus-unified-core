# AutoHaus Unified System AI Blueprint

> **NOTICE TO ALL AI AGENTS (REPLIT, CURSOR, CLAUDE, AUTO-GPT, ETC.):** 
> *Read this document entirely before making architectural, backend, data, or frontend modifications to the AutoHaus ecosystem.*

## 1. The AutoHaus Central Intelligence Layer (CIL)
AutoHaus does not operate like a traditional CRUD application. It is a headless, AI-driven **Central Intelligence Layer (CIL)**. The ecosystem heavily relies on automated document ingestion, LLM parsing, and a centralized data warehouse.

### The Standard Data Flow:
1. **Intake**: A document (e.g., PDF invoice) is uploaded to `01_Unified_Inbox` on Google Drive.
2. **Extraction**: A Cloud Function (or equivalent Python script) wakes up Gemini to parse the PDF, extract entities, and compute derived attributes (e.g., tax calculation).
3. **Storage**: The structured data is inserted directly into Google BigQuery (`autohaus-infrastructure.autohaus_cil.inventory_master`).
4. **Broadcast**: A webhook (`POST`) is fired to notify external consumers (like a web server) of the new payload.
5. **Consumption**: The Python FastAPI backend (`10_IT_AI_Core_Layer/backend`) connects to BigQuery and serves this data via REST endpoints.
6. **Presentation**: Frontends (React/Vite) or external consumers query the Python REST API to render the data.

---

## 2. Infrastructure & Environment Topology
As an AI Agent operating within this project, you must respect the boundaries of the integration stack:
* **Source of Truth (Code)**: GitHub (`autohaus-unified-core`).
* **Source of Truth (Data/Assets)**: Google BigQuery (Structured) & Google Drive (Unstructured/Images).
* **Backend Layer**: Python 3.11+, FastAPI, Uvicorn (`10_IT_AI_Core_Layer/backend`).
* **Frontend Layer**: React (18+), Vite, TypeScript, Tailwind CSS. Served monolithically by FastAPI from the `dist/` directory.
* **Workspaces**: Replit is primarily used for rapid frontend/backend iteration and live previews. Local macOS environments orchestrate structural syncing.

---

## 3. Strict Rules of Engagement for AI Agents

### Rule 1: Respect the Data Hierarchy (No Direct DB Writes from Frontend)
Frontends or UI Agents **must never** attempt to use `@google-cloud/bigquery` or connect to the database directly. All database interactions must be brokered through the Python FastAPI layer (`/api/...`). Frontend AIs exist exclusively to consume the CIL API endpoints.

### Rule 2: API Routing & Deployment Topology
* **Frontend Fetching**: The React frontends are Single Page Applications (SPAs). All fetch requests must use relative paths targeting the `/api/` prefix (e.g., `fetch('/api/inventory/')`).
* **The "Hanging" API Bug**: If an API call hangs infinitely in a new environment like Replit, the Python backend has likely lost its BigQuery Service Account credentials. **Do not rewrite the frontend fetch logic.** Instead, instruct the human or run the credential hydration script: `bash 10_IT_AI_Core_Layer/scripts/replit_init.sh`.

### Rule 3: Extending the Backend (Backend Agents)
When adding new integrations to the core backend (e.g., Twilio SMS, ActiveCampaign, HubSpot):
1. **Isolated Routing**: Create a new isolated route file in `10_IT_AI_Core_Layer/backend/routes/`.
2. **Secret Management**: **Never hardcode API keys.** Document placeholders in `SECRETS_MANIFEST.example.md` and instruct the user to inject them into the environment variables (Replit Secrets or local `.env`).
3. **Database Access**: Adhere to the `get_bq_client` dependency injection pattern for database access, which utilizes Google Cloud ADC (Application Default Credentials) via impersonation.

### Rule 4: Connecting New External AI Agents
If a completely new, autonomous third-party agent (like a voice agent, customer service bot, or scraping agent) needs to interact with AutoHaus:
* **Reads**: It must query the FastAPI `GET` endpoints.
* **Writes**: It must trigger a `POST` request to the appropriate FastAPI webhook/ingestion route. The backend will validate the payload and handle the BigQuery insertion securely. The external agent should never write to BigQuery directly.

---

## 4. UI/UX "Sovereign" Aesthetic Guidelines
When generating user interfaces mapping to the CIL, the visual aesthetic must align with the **Sovereign, High-End Automotive brand** identity.
1. **Dark Mode Default**: Backgrounds should be deep charcoal or pure black (`#0A0A0A`).
2. **Accents**: Use subtle gold, stark white typography, or specific brand colors (e.g., Porsche Red `#E30613` for primary destructive/submit actions). Do not use generic Bootstrap UI colors.
3. **Typography**: Sleek, modern sans-serif fonts (e.g., Inter, Roboto).
4. **Data Integrity**: Admin dashboards must clearly delineate AI-extracted data (e.g., Gemini's reasoning or calculated fields) from raw source data to maintain high confidence in data provenance.
5. **Glassmorphism**: Favor subtle backdrop blurs and semi-transparent boundary borders over solid, heavy containers.
