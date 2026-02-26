# ⚡️ AutoHaus Unified Command Center (UCC) v1.0 - Replit Initialization Packet

> **USER INSTRUCTIONS:**
> 1. Open Replit and create a **brand new Workspace**.
> 2. Open the Replit Agent chat.
> 3. **Copy everything below the dashed line and paste it into the chat.**
> 4. Hit enter and watch the Command Center build itself.

---

### MISSION: Birth the AutoHaus Unified Command Center (UCC) v1.0
**Context:** The Central Intelligence Layer (CIL) Backend v2.0 is live. The immutable `system_audit_ledger` and the `business_ontology` are active. 
**Objective:** Initialize the decoupled, internal-only React Dashboard. You are building the "Hub" in a Hub-and-Spoke architecture.

### 1. Infrastructure Setup:
- **Action:** Initialize a new React + Vite + Tailwind v4 project.
- **Process:** The UI must be a "dumb terminal" that consumes the CIL API exclusively. Absolutely NO direct database connections (No Firebase, No Supabase, No direct BigQuery).
- **Routing:** Use React Router for navigation.
- **State:** Use React Context or standard Hooks for state management.

### 2. The "Sovereign/Veblen" UI/UX Build:
Enforce this strict high-end automotive aesthetic:
- **Theme:** Deep Zinc (`bg-zinc-950` or `#0A0A0A`) for the main background. Use `bg-zinc-900` for cards.
- **Typography:** Pure white (`text-white`) for primary text, muted (`text-zinc-400`) for secondary.
- **Accent Colors:** 'Porsche Red' (`#E30613` or `bg-red-600`) for primary/destructive actions. Subtle Gold (`#C5A059`) for highlights or confidence indicators.
- **Layout:** A persistent Left-Hand Sidebar for navigation, with a top-right user profile indicator ("Logged in as: Super Admin").

### 3. Required Dashboard Views (The Skeleton):
Generate the following core views with modular components (e.g., `App.tsx`, `AdminDashboard.tsx`, `AuditLog.tsx`):

*   **View A: Inventory Matrix (The Anchor)**
    *   A data table showing mock vehicles (make, model, VIN, price, status).
    *   Must include status badges (e.g., "Pending", "Live").
    *   *The Action Hook:* Each "Pending" vehicle must have a **"Promote to Live"** button.

*   **View B: System Ledger (The Audit Trail)**
    *   A real-time table view designed to display the `system_audit_ledger`.
    *   Columns: Timestamp, Actor (User/AI), Action Type, Entity ID, Changes.

*   **View C: The Brain Feed (AI Telemetry)**
    *   A terminal-style component or scrolling feed showing Gemini's real-time extraction logs and "Confidence Scores".

### 4. Functional Handshake (The Architecture Test):
- **Action:** Wire the "Promote to Live" button to target the backend endpoint.
- **The Target:** `POST /api/inventory/promote`
- **The Payload:** `{ "vehicle_id": "PORSCHE-911-001", "actor_id": "UI_Agent" }`
- **Optimistic UI:** When the button is clicked, immediately show a loading spinner, then update the UI state to "Live" assuming a 200 OK response. This triggers the backend dual-commit (Update Inventory + Write Audit Log).
- **Rule:** Assume the API is hosted externally. Use a configurable base URL (e.g., via `import.meta.env.VITE_CIL_API_URL` or a proxy setup).

### 5. Identity & Ontology Integration:
You must strictly align your hardcoded UI labels with the AutoHaus Business Ontology:
- "Carbon LLC" = Master Holding Entity
- "Lane A" = KAMM LLC (Retail Sales & Financing)
- "Lane B" = AstroLogistics LLC (Fleet Operations)
- "Lane Service" = Diagnostics & Recon

**Final Command:** Generate the setup and the React components now. **Report the exact phrase 'COMMAND CENTER INITIALIZED' once the UI is successfully rendering the mock Porsche inventory and the layout is complete.**
