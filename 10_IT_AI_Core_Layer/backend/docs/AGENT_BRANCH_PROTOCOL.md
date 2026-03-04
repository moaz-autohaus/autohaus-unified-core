# AUTOHAUS C-OS — AGENT BRANCH & HANDOFF PROTOCOL
## Governing Rule for Antigravity and Replit
Version 1.1 · March 4, 2026
Status: MANDATORY — both agents must read this before any git operation

---

## The Two-Branch Model

```
dev-antigravity    ← Antigravity uses for multi-file features and new components
main               ← Integration point and live truth; Replit always pulls from here
dev-replit         ← Replit uses for frontend-only work
```

**Branch routing rules (effective March 4, 2026):**

- **Small fixes, single-file patches, config changes, seed corrections →
  commit directly to main**
- **Multi-file features, new components, schema changes, membrane work →
  dev-antigravity first, Moaz reviews pre-merge confirmations, Antigravity executes
  the merge to main on SOVEREIGN authorization**
- Antigravity always reports the commit hash after every push, regardless of branch
- Replit always pulls from main and confirms hash before restarting

Neither agent pushes directly to `dev-replit` (Replit's branch) unless operating as Replit.
Neither agent touches the other's directory under any circumstances.

---

## Directory Ownership — Hard Boundary

ANTIGRAVITY OWNS:
  backend/
  scripts/
  auth/
  agents/
  memory/
  membrane/
  registry/

REPLIT OWNS:
  frontend/
  src/
  public/
  dist/

If a file is in the other agent's directory, do not touch it.
If a backend fix is needed and you are Replit, write an API spec
describing what you need and hand it to Antigravity. Never edit
backend files directly. This is what caused the media_routes.py
conflict and it must never happen again.

---

## Commit Routing Decision Tree

```
Is this a single-file change or small config fix?
  YES → commit directly to main, report hash
  NO  → Is this a new component, schema change, or membrane work?
          YES → commit to dev-antigravity, run pre-merge confirmations,
                await SOVEREIGN authorization, then merge to main
          NO  → use judgment; default to main for speed
```

---

## The Handoff Sequence

### When Antigravity finishes multi-file backend work:

1. Commit and push to dev-antigravity:
   git add backend/ scripts/ auth/ agents/ memory/ membrane/ registry/
   git commit -m "feat: <description>"
   git push origin dev-antigravity

2. Run all four pre-merge confirmations:
   - Alias/content verification
   - git log main..origin/dev-antigravity --oneline
   - git diff main origin/dev-antigravity --name-only (no frontend files)
   - git log origin/dev-antigravity --oneline -1

3. Report results to Moaz and await SOVEREIGN authorization.

4. On authorization, execute the merge:
   git checkout main
   git fetch origin
   git pull origin main
   git merge origin/dev-antigravity --no-ff -m "merge: <description>"
   git push origin main

5. Report the post-merge HEAD hash.

---

### When Antigravity makes a single-file fix or config patch:

1. Ensure you are on main:
   git checkout main

2. Commit and push directly:
   git add <file>
   git commit -m "fix: <description>"
   git push origin main

3. Report the commit hash immediately.

---

### When Replit needs Antigravity's latest backend (most common):

Run in Replit shell:
  git fetch origin
  git pull origin main
  git log --oneline -1

Confirm the hash matches what Antigravity reported.
Restart the FastAPI server after pull (Stop → Run in Replit).
Confirm WS LIVE before running any tests.

---

### When Replit finishes frontend work:

1. Commit and push to dev-replit:
   git add frontend/ src/ public/
   git commit -m "feat: <description>"
   git push origin dev-replit

2. Report the commit hash to Moaz.

3. Moaz merges dev-replit to main when ready.

---

## The Telemetry Loop

```
Antigravity builds → commits (main or dev-antigravity) → reports hash
Replit pulls from main → restarts server → confirms hash + WS LIVE
Replit executes test → pastes console output to Moaz
Moaz analyzes → instructs next action
Antigravity builds fix → commits → reports hash
Loop repeats
```

---

## Conflict Prevention Rules

1. NEVER edit a file in the other agent's directory — ever.
   If you think you need to, stop and write an API spec instead.

2. For multi-file backend work, NEVER push to main directly.
   Use dev-antigravity and await SOVEREIGN authorization to merge.

3. For single-file fixes, commit directly to main. No ceremony needed.

4. ALWAYS rebase (never merge) between agent branches when syncing
   dev branches to each other. Rebase keeps linear history.

5. ALWAYS report the commit hash after every push — every single one.
   No hash = no confirmation = do not proceed.

6. ALWAYS restart the FastAPI server after a pull on Replit.
   Old code running in memory causes ghost bugs that are hard to trace.

7. If git state breaks at any point:
   git merge --abort          (if mid-merge)
   git rebase --abort         (if mid-rebase)
   git fetch origin
   git reset --hard origin/main   (for either agent — main is the safe reset point)

---

## What Triggered This Protocol

The media_routes.py conflict on March 3, 2026 happened because:
- Replit edited a backend file (media_routes.py) to add HITL fallback logic
- Antigravity also modified the same file independently
- Both pushed to main directly without coordination
- The merge conflict wiped work from both agents

The correct resolution was:
- Replit should have written an API spec describing the HITL fallback need
- Antigravity should have implemented it in backend/routes/media_routes.py
- Replit should have pulled from main to get the fix

This protocol prevents that class of conflict from ever recurring.

---

## Branch Reference

  main              Integration point and live truth. Replit always pulls from here.
  dev-antigravity   Antigravity's staging branch for multi-file work.
  dev-replit        Replit's working branch. Frontend only.
  replit-agent      Legacy branch. Do not use. To be deleted.

---

## Batch Ingestion — Warm-Up Rule

Before running batch_ingest.py, the script automatically pings the server.
If the ping fails, the script aborts with a clear message.
Do not disable this check. A sleeping Replit instance will drop connections
mid-extraction, producing false exception failures with no HTTP status.

Always:
1. Wake Replit (hit Run, wait for WS LIVE)
2. Confirm WS LIVE in the console
3. Run the batch immediately — do not let Replit idle again before the first file

---

AutoHaus · Carbon LLC · C-OS v3.1.1-Alpha
Agent Branch Protocol v1.1 · March 4, 2026
MANDATORY — paste this into both Antigravity and Replit at session start
