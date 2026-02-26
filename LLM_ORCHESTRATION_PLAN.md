# AutoHaus CIL: Multi-Model Orchestration Plan
# Goal: Build the Master Blueprint using Gemini Flash and Claude 4.6 to conserve Gemini Pro 3.1 quota.

This plan details how to split the remaining implementation work between less expensive or higher-rate-limit models while reserving Gemini Pro 3.1 strictly for the architectural validation and complex reasoning tasks where it excels.

---

## 1. The Core Strategy: Role Division

We need to stop using Gemini Pro 3.1 to write standard Python boilerplate or SQL schemas.

| Model | Role in Implementation | Use Cases |
| :--- | :--- | :--- |
| **Claude Sonnet 4.6** | **The Code Builder** | Writing FastAPI endpoints, BigQuery DDLs, React UI components (Plates), and pipeline scaffolding. It uses the Blueprint to generate production code. |
| **Gemini Flash** | **The Pipeline Worker**| Used *inside* the pipeline code for high-volume, low-latency tasks: format routing, simple text classification, and extracting standard fields from clear OCR text. |
| **Gemini Pro 3.1** | **The Brain (Reserve)** | Used *sparingly*: complex entity resolution (fuzzy matching), resolving KAMM compliance ambiguities, and making architectural checks. |
| **Claude Opus 4.6** | **Complex Scaffolding**| Use if Sonnet struggles with multi-file architectural refactors (e.g., retrofitting event sourcing across a large codebase). |

---

## 2. Micro-Order Execution Plan (Model Assignments)

Here is exactly how you execute the 9-Step Micro-Order defined in Blueprint v2.1, specifying *which* AI to use for each step.

### Phase 1: Ingestion & Validation

*   **Step 1: Foundational Ledger (`cil_events`)**
    *   **Workflow:** Ask **Claude Sonnet 4.6** to write the BigQuery Python client and the schema execution scripts, relying entirely on the DDLs in the Blueprint.
*   **Step 2: Document Ingestion (`documents` + Dedup)**
    *   **Workflow:** Ask **Claude Sonnet 4.6** to write the `dedup_gate.py` (SHA-256 logic).
*   **Step 3: Queues & Reliability**
    *   **Workflow:** Ask **Claude Sonnet 4.6** to write a simple FastAPI `BackgroundTasks` queue to start (we can upgrade to Cloud Tasks later).
*   **Step 4: Format & OCR Rules**
    *   **Workflow:** Ask **Claude Sonnet 4.6** to write `format_router.py`. Use **Gemini Flash** (via API) in the code to handle any text classification that `python-magic` can't solve.

### Phase 2: Knowledge Extraction

*   **Step 5: Master Entities v0.1**
    *   **Workflow:** **Claude Sonnet 4.6** writes the DDLs for the 5 entities.
*   **Step 6: Schema Engine (The only heavy Gemini Pro 3.1 use)**
    *   **Workflow:** Use **Gemini Pro 3.1** *once* to generate the 8 strict YAML schemas based on your business logic. Save them. You never need Pro 3.1 for this again.
*   **Step 7: Extraction & Linking**
    *   **Workflow:** The pipeline code (written by Claude) will call **Gemini Flash** for standard extraction (passing the YAML schema). Flash is more than capable of structured extraction. We only call **Gemini Pro 3.1** if Flash returns a confidence < 0.85 on an entity link.

### Phase 3: Governance & Launch

*   **Step 8: HITL & Governance**
    *   **Workflow:** **Claude Sonnet 4.6** is exceptional at React/Vite. Give it the HITL chapter of the Blueprint and ask it to build the "Pending Corrections" UI and the `/api/hitl/` state machine.
*   **Step 9: Seeding Toolchain**
    *   **Workflow:** **Claude Sonnet 4.6** writes the overarching batch script. The script uses **Gemini Flash** to process the documents cheaply, only falling back to **Gemini Pro 3.1** for ambiguous edge cases or KAMM damage disclosures.

---

## 3. The 90/10 Hybrid Pipeline (How the Code Will Run)

To conserve quota *while the system is running*, the actual C-OS pipeline code should be written to use a waterfall approach for LLM calls:

1.  **Fast Path (Code):** Can deterministic python solve it? (e.g., exact VIN match, regex on email). If yes, DO NOT call an LLM.
2.  **Flash Path (Low Cost):** If it requires AI (e.g., extracting invoice fields), call Gemini Flash. It is fast and cheap.
3.  **Pro Path (High Cost):** ONLY call Gemini Pro 3.1 if Flash flags the document as `requires_human_review = TRUE` due to low confidence, OR if it's a KAMM compliance document that needs complex reasoning.

---

## What You Should Do Right Now

Start your next prompt to **Claude Sonnet 4.6**, providing it the `CIL_MASTER_BLUEPRINT_v2.0.md` file, and say:

> "I need you to act as the Code Builder for this project. Read the Master Blueprint. Our immediate task is Phase 1, Step 1: writing the BigQuery schema setup script for the `cil_events` table and the Pydantic models for the Event Payload Registry. Write the Python code."
