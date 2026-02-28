# AUTOHAUS CIL: PHASE 9 — FRONTEND BUILD INSTRUCTIONS
**Target:** Replit AI Agent / React Frontend Developer
**Context:** The Python FastAPI backend has just completed "Phase 8: The Integration & Enrichment Engine." It now automatically enriches incoming entities with external APIs (like NHTSA) and proactively proposes actions (like drafting emails, proposing vehicle listings, or syncing to QuickBooks).

**Crucially, the backend operates on a "Sandbox-First" architecture.** It does not send emails or spend money automatically. It places these proposed actions into an approval queue.

**Your Goal as the Frontend Developer:** Build the operational UI components that allow the CEO to visualize the enriched data and approve/reject the sandbox proposals. 

You do not need to alter any Python backend code. Assume these endpoints exist and handle errors gracefully.

---

## TASK 1: THE PROVENANCE BADGE SYSTEM

When viewing a Vehicle or Person profile, the data you receive from the backend will now include `authority_level` and `corroboration_count`. You must build a `ProvenanceBadge` component to display next to data fields (like VIN, Make, Model, or safety ratings).

### Authority Levels & Visuals:
1. **`SOVEREIGN` (Highest):** Manually overridden by the CEO. 
   - *Visual:* Solid Gold Crown icon.
2. **`VERIFIED` (High):** Seeded from the Master Registry or human-confirmed.
   - *Visual:* Solid Green Checkmark icon.
3. **`AUTO_ENRICHED` (Medium-High):** Data pulled from authoritative external APIs (NHTSA, State Business Registry).
   - *Visual:* Solid Blue Shield icon. Tooltip should say "Verified by [source_type, e.g. NHTSA]".
4. **`EXTRACTED` (Medium):** AI OCR data that has been approved.
   - *Visual:* Solid Purple File icon.
5. **`PROPOSED` (Low):** Unverified AI extraction in the sandbox.
   - *Visual:* Yellow pulsing Alert/Eye icon.
6. **`UNVERIFIED` (Lowest):** Raw stub data.
   - *Visual:* Gray question mark.

*Use Lucide-React icons (e.g., `<Crown />`, `<ShieldCheck />`, `<FileText />`).*

---

## TASK 2: THE "ACTION CENTER" (SANDBOX INBOX)

Create a new view named `ActionCenter.jsx`. This is the operational inbox for the CIL where the CEO reviews what the AI wants to do.

### Architecture:
1. Fetch pending proposals by querying the backend. (Assume `GET /api/hitl/queue` returns a list of proposed events).
2. The UI should display a clean, high-contrast list or grid of "Proposal Cards."
3. Every card must have a massive, satisfying **"Approve & Execute"** (Green) button and a **"Reject / Edit"** (Red/Gray) button.

### Card Types to Support:
The backend generates different payloads depending on the event type.

**A. Email Draft Proposal (`event_type: "EMAIL_DRAFTED"`)**
- *Display:* Recipient email, Subject line, and a truncated preview of the Body.
- *Context:* "The system wants to send this email to [Recipient]."

**B. Listing Syndication Proposal (`event_type: "LISTING_PROPOSED"`)**
- *Display:* The targeted Vehicle (VIN/Make/Model), the AI-generated listing description, and the target platforms (e.g., CarGurus, Facebook).
- *Context:* "The system wants to push this listing to external platforms."

**C. QuickBooks Journal Proposal (`event_type: "QUICKBOOKS_JOURNAL_PROPOSED"`)**
- *Display:* A summary of the financial transaction (e.g., "Vehicle Purchase - $15,000 to Account 1400 (Inventory)").
- *Context:* "The system wants to sync this transaction to QuickBooks."

### Action Handling:
When "Approve" is clicked, send a `POST /api/hitl/{event_id}/approve` request to the backend. Optimistically remove the card from the UI upon success.

---

## TASK 3: THE PUBLIC API MOCK DASHBOARD

The backend now exposes a strictly filtered Public API meant for the customer-facing AutoHaus website. We need a dev-only tool to test this.

Create a hidden or dev-only `PublicApiTest.jsx` view with two sections:

1. **Mock Public Inventory Grid**
   - *Action:* `GET /api/public/inventory`
   - *Requirement:* Render the vehicles returned. Prove that it ONLY shows vehicles with `status = 'AVAILABLE'` and that internal costs (like wholesale or recon costs) are completely hidden, showing only `listing_price`.

2. **Mock Public Intake Form**
   - *Action:* Provide inputs for Name, Phone, Email, and Interest VIN.
   - *Execution:* On submit, send a `POST /api/public/lead` request with this JSON payload:
     ```json
     {
       "name": "Test User",
       "phone": "555-0199",
       "email": "test@example.com",
       "interest_vin": "WBA1234..."
     }
     ```
   - *Requirement:* Show a success toast when the backend accepts the lead. (Behind the scenes, the backend will asynchronously create a Person entity and fire a notification to the CEO).

---

## DESIGN SYSTEM REQUIREMENTS
- **Theme:** Dark mode by default. Deep blacks, charcoal grays, and highly saturated accent colors for statuses.
- **Density:** High. This is an operational dashboard, not a consumer app.
- **Icons:** Standardize entirely on `lucide-react`.
- **State Management:** Use standard React hooks (useState, useEffect). If you prefer `react-query` or `swr` for data fetching, that is acceptable.

Please proceed with building these components and routing them into the main application shell.
