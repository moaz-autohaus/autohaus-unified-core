# Agent Coordination Protocol
This document defines the branching and synchronization rules for all AI agents working on the AutoHaus CIL codebase (Antigravity and Replit Agent).

## 1. Swimlane Strategy (Branching)
To prevent merge conflicts and over-writing work, each agent environment must operate on its own dedicated Git branch.

* **GitHub `dev-antigravity`:** The branch for backend development, schema enhancements, and CIL logic. Always controlled by the Antigravity agent.
* **Replit `dev-replit`:** The branch for frontend experimentation, rapid UI iteration, and integration testing on Replit. Always controlled by the Replit Agent.
* **GitHub `main`:** The deployment and production-ready source of truth.

## 2. Sync Rules
### Case A: Replit pulling backend updates from Antigravity
When Antigravity pushes backend fixes (like event loop fixes or schema updates) to `dev-antigravity`, the Replit Agent must pull them into its local `dev-replit` branch.

**Prompt for Replit Agent:**
> "Merge `origin/dev-antigravity` into your current branch `dev-replit` to pick up the latest backend fixes. Prioritize keeping backend logic from `dev-antigravity` if conflicts arise in `backend/`."

### Case B: Antigravity pulling Replit UI improvements
When Replit pushes UI/Frontend fixes to `main` (after a manual pull request), Antigravity must pull them into `dev-antigravity`.

**Workflow:**
1. Replit Agent pushes `dev-replit` to GitHub.
2. User merges the Pull Request from `dev-replit` -> `main`.
3. Antigravity merges `main` into `dev-antigravity`.

## 3. Communication Channel
Agents should check for the existence of this file at the start of every session to confirm their current active branch and sync status.

* **Active Antigravity Branch:** `dev-antigravity`
* **Target Replit Branch:** `dev-replit`
