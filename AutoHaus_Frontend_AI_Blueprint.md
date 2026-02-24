# AutoHaus Unified Frontend AI Agent Blueprint

> **NOTICE TO ALL AI AGENTS (REPLIT, CURSOR, CLAUDE, ETC.):** 
> *Read this document entirely before making any modifications to the frontend UI, adding new pages, or touching the API routing.*

## 1. System Vision & The CIL (Central Intelligence Layer)
AutoHaus operates on a headless, API-first **Central Intelligence Layer (CIL)**. The frontend does not own the data, does not parse documents, and does not talk to the database directly. 
1. **Intake**: A PDF invoice drops into 01_Unified_Inbox (Google Drive).
2. **Extraction**: A Cloud Function triggers Gemini to parse the PDF.
3. **Storage**: Data is structured and inserted via SQL into Google BigQuery (`autohaus_cil.inventory_master`).
4. **Presentation**: The Python FastAPI backend serves this data via REST (`/api/...`).
5. **Consumption**: Replit (or any frontend) consumes the REST API and builds the UI.

**Your job as a Frontend Agent is exclusively to consume the CIL API endpoints and present them beautifully.**

---

## 2. Infrastructure & Tech Stack
If you are analyzing code or diagnosing issues, assume the following stack:
* **Frontend**: React (18+), Vite, TypeScript, Tailwind CSS. Served as a Single Page Application (SPA).
* **Backend**: Python 3.11+, FastAPI, Uvicorn.
* **Database**: Google BigQuery (Data warehouse).
* **Authentication**: Google Cloud Service Accounts (ADC - Application Default Credentials).
* **Workspace**: Replit for frontend rapid deployment, GitHub for source of truth.

---

## 3. Strict Rules for Frontend Generation & Modification

### Rule 1: Never Bypass the Backend
Frontend code (React/JS/TS) **must never** attempt to use `@google-cloud/bigquery` or connect to the database directly. You must only fetch data via the Python FastAPI layer (`10_IT_AI_Core_Layer/backend/main.py`).

### Rule 2: Web API Routing & The "Hanging" Bug
All fetch requests in the frontend must use relative paths targeting the `/api/` prefix (e.g., `fetch('/api/inventory/?public=true')`). 
* **If API calls "hang" infinitely**: The Replit Python backend has likely lost its BigQuery credentials. **Do not rewrite the frontend fetch logic.** Instead, instruct the human developer (or use your shell) to run:
  `bash 10_IT_AI_Core_Layer/scripts/replit_init.sh`
  This hydrates the `auth/service_account.json` file required by the Python BigQuery client.

### Rule 3: The Dist Folder & Static Serving
The React application is built via Vite. 
* To build: `npm run build`
* The output goes to the root `dist/` folder.
* The Python backend serves the UI by taking over the root route (`/`) and explicitly pointing to `../../dist/index.html`. 
* **Never alter the backend `DIST_DIR` target** unless you are fundamentally changing the Replit workspace layout.

### Rule 4: Handling the '/admin' Route
Because the site is a Single Page Application:
* The FastAPI backend has a catch-all route that redirects 404s back to `index.html`. 
* React Router handles the actual `/admin` navigation. 
* To add new protected pages or dashboards, add them to the React Router DOM. Do not add HTML template rendering to the Python backend.

---

## 4. Design & UI/UX Guidelines
As an AI generating interfaces for AutoHaus, your aesthetic must align with a **Sovereign, High-End Automotive brand**.
1. **Dark Mode Default**: Backgrounds should be deep charcoal or pure black (`#0A0A0A`).
2. **Accents**: Use subtle gold or stark white typography for high contrast. Do not use generic, vibrant bootstrap colors (no bright blue buttons).
3. **Typography**: Sleek, modern sans-serif fonts (e.g., Inter, Roboto).
4. **Data Presentation**: Admin tables (`/admin`) must clearly delineate extracted Gemini data (like Tax Calculations, VINs, and JSON arrays) in clean, readable grids.
5. **Glassmorphism**: Use subtle backdrop blurs for navigation plates and floating cards to create depth.

---

## 5. Extensibility & Connecting New Agents
If a new AI agent needs to add a completely new integration (e.g., Twilio SMS, automated emails, or calendar bookings):
1. **Register the capability in the Backend**: Create a new route in `10_IT_AI_Core_Layer/backend/routes/`.
2. **Secure the secret**: Place the API key placeholder in `SECRETS_MANIFEST.example.md` (never commit real keys).
3. **Expose an endpoint**: Have the backend expose a clean `POST /api/your_feature`.
4. **Build the UI**: Have the React frontend call the new `/api/your_feature` endpoint.
