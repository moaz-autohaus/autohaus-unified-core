# AutoHaus AI Execution Rules

## 1. Execution Modes
- **Fast Mode**: For single-file logic, typos, formatting, and standard DDL updates.
- **Planning Mode**: For architectural changes, multi-file refactors (like Phase 3 membrane builds), or complex async handling. **Wait for human sign-off on the plan before coding.**

## 2. Behavioral Constraints (Quota Prevention)
- **The Rule of Two**: If a build or deployment fails TWICE consecutively, STOP. Report the console error and wait for human input. Do not attempt a third automated fix.
- **Single Responsibility**: Perform one logic change per turn. Do not refactor unrelated code while fixing a bug.
- **Local Verification First**: Always run local scripts (e.g., `check_secrets.py`, `pilot_test.py`) before pushing to Cloud Run.
- **No Guessing**: If a dependency, tool, or parameter is unclear, ASK. Do not guess and trigger a failing loop.
- **Commit Early**: Recommend/Commit changes after every completed task milestone.

## 3. The Golden Rules of AutoHaus CIL
1. **Never Bypass the API**: Frontend MUST route through the FastAPI backend. NEVER talk to BQ/Drive directly.
2. **Never Hardcode Secrets**: Use Secret Manager or environment variables.
3. **Immutable State**: Follow the "Sovereign Spine" pattern. Append new claims; do not overwrite existing ones.

## 4. UI / UX Aesthetic
- Enforce the "Luxe Dark" theme: Pure black background, bright white text, Porsche Red (`#E30613`) for primary actions, subtle Gold (`#C5A059`) for highlights. No generic Tailwind colors.

## 5. Workflow Protocol
- Before any implementation, provide a **2-line summary** of the intended path.
- In Debug threads: Isolate the single failing file. If failure persists 3 times, close the thread and start fresh with just the context of the bug.
