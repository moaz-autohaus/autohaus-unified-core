# AUTOHAUS C-OS — AGENT BRANCH & HANDOFF PROTOCOL
## Governing Rule for Antigravity and Replit
Version 1.0 · March 3, 2026
Status: MANDATORY — both agents must read this before any git operation

---

## The Two-Branch Model

```
dev-antigravity    ← Antigravity works here exclusively (backend/ only)
dev-replit         ← Replit works here exclusively (frontend/ only)
main               ← Integration point, merged by Moaz only
```

Neither agent pushes directly to main.
Neither agent touches the other's directory under any circumstances.
main is the only branch Moaz merges into.

---

## Directory Ownership — Hard Boundary

ANTIGRAVITY OWNS:
  backend/
  scripts/
  auth/
  agents/
  memory/
  membrane/

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

## The Handoff Sequence

### When Antigravity finishes backend work:

1. Commit and push to dev-antigravity:
   git add backend/ scripts/ auth/ agents/ memory/ membrane/
   git commit -m "feat: <description>"
   git push origin dev-antigravity

2. Report the commit hash to Moaz.
   Example: "Pushed d3cbedd to dev-antigravity. Replit can pull."

3. If Replit needs this work immediately, instruct Replit to rebase:
   git fetch origin
   git rebase origin/dev-antigravity
   git push origin dev-replit --force-with-lease

---

### When Replit finishes frontend work:

1. Commit and push to dev-replit:
   git add frontend/ src/ public/
   git commit -m "feat: <description>"
   git push origin dev-replit

2. Report the commit hash to Moaz.
   Example: "Pushed a1b2c3d to dev-replit. Antigravity can pull."

3. If Antigravity needs this work, instruct Antigravity to rebase:
   git fetch origin
   git rebase origin/dev-replit
   git push origin dev-antigravity --force-with-lease

---

### When Replit needs Antigravity's latest backend (most common):

Run in Replit shell:
  git fetch origin
  git rebase origin/dev-antigravity
  git log --oneline -1

Confirm the hash matches what Antigravity reported.
Restart the FastAPI server after rebase (Stop → Run in Replit).
Confirm WS LIVE before running any tests.

---

### When Moaz merges to main (integration checkpoint):

Moaz runs locally or instructs Antigravity:
  git checkout main
  git fetch origin
  git merge origin/dev-antigravity
  git merge origin/dev-replit
  git push origin main

This is the only path to main. Neither agent merges to main directly.

---

## The Telemetry Loop

```
Antigravity builds → pushes to dev-antigravity → reports hash
Replit rebases from dev-antigravity → restarts server → confirms hash
Replit executes test → pastes console output to Moaz
Moaz analyzes → instructs next action
Antigravity builds fix → pushes → reports hash
Loop repeats
```

---

## Conflict Prevention Rules

1. NEVER edit a file in the other agent's directory — ever.
   If you think you need to, stop and write an API spec instead.

2. NEVER push to main directly.
   main is Moaz's integration checkpoint only.

3. ALWAYS rebase, never merge between agent branches.
   Rebase keeps a linear history. Merge commits create noise and
   make rollbacks harder.

4. ALWAYS report the commit hash after every push.
   The hash is the cryptographic proof the code landed.
   No hash = no confirmation = do not proceed.

5. ALWAYS restart the FastAPI server after a rebase on Replit.
   Pulling new code without restarting means the old code is still
   running in memory. This causes ghost bugs that are hard to trace.

6. If git state breaks at any point:
   git merge --abort          (if mid-merge)
   git rebase --abort         (if mid-rebase)
   git fetch origin
   git reset --hard origin/dev-antigravity   (for Antigravity)
   git reset --hard origin/dev-replit        (for Replit)

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
- Replit should have rebased from dev-antigravity to get the fix

This protocol prevents that class of conflict from ever recurring.

---

## Branch Reference

  main              Integration point. Moaz merges here only.
  dev-antigravity   Antigravity's working branch. Backend only.
  dev-replit        Replit's working branch. Frontend only.
  replit-agent      Legacy branch. Do not use. To be deleted.

---

## Required Action — Current Session

Before resuming Test.pdf ingestion, Antigravity must:

1. Summarize what is in dev-antigravity (20 commits ahead of main).
   Run: git log main..dev-antigravity --oneline
   Report the list back to Moaz.

2. Confirm no frontend files were modified in any of those 20 commits.
   Run: git diff main dev-antigravity --name-only | grep -v "^backend\|^scripts\|^auth\|^agents\|^memory\|^membrane"
   If any frontend files appear, flag them before merging.

Replit must:
1. Stay on main at d3cbedd until Moaz gives the merge signal.
2. Run Test.pdf ingestion from current state.
3. Paste full console output back for analysis.

---

AutoHaus · Carbon LLC · C-OS v3.1.1-Alpha
Agent Branch Protocol v1.0 · March 3, 2026
MANDATORY — paste this into both Antigravity and Replit at session start
