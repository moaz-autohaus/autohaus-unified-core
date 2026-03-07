# AutoHaus CIL — Project Context

## 1. Project Goal
Orchestrate the **AutoHaus Central Intelligence Layer (CIL)**: A 10-layer governance-first architecture that extracts, validates, and manages automotive business facts using Gemini AI and BigQuery.

## 2. Tech Stack
- **Backend:** Python 3.12+, FastAPI, Uvicorn.
- **Database:** Google BigQuery (Append-only immutable Event Store).
- **Core AI:** Gemini 1.5/2.x (Flash & Pro), Vertex AI.
- **Frontend:** React (Vite), Tailwind CSS (Porsche-inspired Luxe Dark theme).
- **Infrastructure:** Google Cloud Run, Secret Manager, Cloud Build.

## 3. Directory Map & Critical Paths
- `/10_IT_AI_Core_Layer/backend/`: Primary logic workspace. 
- `/10_IT_AI_Core_Layer/backend/database/`: BQ schemas and client logic.
- `/10_IT_AI_Core_Layer/backend/pipeline/`: Extraction, Conflict Detection, and HITL logic.
- `/10_IT_AI_Core_Layer/backend/docs/`: **The Source of Truth.** READ THESE FIRST.
  - `CIL_THREE_LAYER_ARCHITECTURE.md`: Structural boundaries.
  - `CLAIMS_AND_EVENTS_CANON.md`: Data integrity and append-only patterns.
- `attached_assets/`: Golden test files (e.g., `Test.pdf`).

## 4. Patterns & Canonical Examples
- **Immutable State:** We never `UPDATE` data values; we append new claims or assertions.
- **Verification Example:** `backend/scripts/setup_bq_claims.py` (Standard DDL pattern).
- **Service Pattern:** `backend/pipeline/hitl_service.py` (Standard append-only status pattern).

## Git Discipline
- Run `git status` before starting any task to understand current state
- Commit after every completed subtask with a descriptive message
- Never end a session without committing all completed work
- Never use `git add -A` — always stage specific files by name
- Commit message format: `type(scope): description`
  - Types: feat, fix, chore, docs, refactor
  - Example: `feat(compliance): add title_bottleneck route`
