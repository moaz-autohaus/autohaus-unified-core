# AutoHaus Unified System - Master AI Governance Packet

**ATTENTION AI AGENTS (Replit, Cursor, Claude, Windsurf, auto-GPT):**
*If you have been instantiated to edit, read, or expand the AutoHaus workspace, you are contractually bound by the rules in this packet. Do not begin writing code or changing files until you have fully assimilated this document.*

---

## 1. YOUR ROLE & PURPOSE
You are operating within the **AutoHaus Central Intelligence Layer (CIL)**. This is not a standalone web app; it is a 10-layer enterprise architecture. Your purpose is to assist developers (like Ahsin) in modifying the React UI or adding backend extensions **WITHOUT breaking the intelligence pipeline**.

---

## 2. THE GOLDEN RULES OF THE AUTO-HAUS CIL
Violating these rules breaks the production environment:
1. **Never Bypass the API**: The Frontend (React/Vite) MUST NEVER talk to Google BigQuery or Google Drive directly. All data requests must route through relative paths targeting the Python backend (e.g., `fetch('/api/inventory/')`).
2. **Never Hardcode Secrets**: GCP Service Accounts, API Keys, and Webhook URLs must NEVER be hardcoded. Read from environment variables. If a new API key is needed, document it as a placeholder in `SECRETS_MANIFEST.example.md` and instruct the human how to add it to Replit Secrets or their local `.env`.
3. **Do Not Touch Data Schemas Without Permission**: BigQuery schema definitions belong to the master orchestrators. If the UI needs a new data field, tell the human that the Core ingestion scripts must be updated first.

---

## 3. UI / UX DESIGN SYSTEM (Frontend Agents)
If you are generating or modifying the React/Tailwind frontend, enforce this strict high-end automotive aesthetic:
* **Backgrounds & Surfaces**: Use ultra-dark themes. The standard background should be pure black (`bg-black` or `bg-zinc-950`). Use `bg-zinc-900` for elevated cards.
* **Typography**: Clean, modern spacing. Primary text is bright white (`text-white`), secondary text is muted (`text-zinc-400`). 
* **Accent Colors**: 
  * Primary Action / Destructive: Porsche Red (`#E30613` or roughly `bg-red-600`).
  * Highlight / Luxury Polish: Subtle Gold (`#C5A059`) for minor borders or highly strategic icons.
  * **Prohibition**: DO NOT use default Tailwind blue, purple, or green unless explicitly matched to a brand (e.g., green for a success toast).
* **Components**: Use subtle glassmorphism (backdrop-blur) for floating components. Ensure the UI looks "Sovereign" and mission-critical. Use skeletons while loading.
* **Integrity**: When displaying AI-generated data (e.g., Gemini's Document Extractions), mark it visually (e.g., with a small icon or distinct border) so the user knows it was synthesized by an LLM.

---

## 4. CREDENTIAL HANDLING & THE "HANG" BUG (Backend/Replit Agents)
If you are asked to debug why the Replit Preview or `/admin` page is loading endlessly or why `/api/inventory` requests are failing to return data:
* **The Diagnosis**: The `SERVICE_ACCOUNT_JSON` secret exists in Replit's vault but is not "hydrated" (written to the actual file system where the Python Google Cloud client expects it).
* **The Fix**: **Do not rewrite the data fetch logic.** Inform the user to run the hydration script in the Replit Shell:
  `bash 10_IT_AI_Core_Layer/scripts/replit_init.sh`
* Once run, tell the human to immediately restart the server using the main "Run" button.

---

## 5. EXTENSIBILITY (How to add new features)
If Ahsin asks you to build a new feature (e.g., SMS notifications, a new dashboard widget):
1. **Backend First**: Create a new route file in `10_IT_AI_Core_Layer/backend/routes/`.
2. **API Contract**: Define a clear FastAPI endpoint returning JSON.
3. **Frontend Integration**: Hook the React UI to that endpoint.
4. **Deploy**: The FastApi `main.py` is configured to serve the built React output from `../../dist`. If the frontend is changed, you must instruct the shell to run `npm run build` so `main.py` reflects the changes.

---
*End of Packet. Standardize your context and await the user's prompt.*
