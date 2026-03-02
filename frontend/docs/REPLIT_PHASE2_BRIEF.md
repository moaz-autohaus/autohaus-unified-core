# Replit Phase 2 Briefing

## 1. COORDINATION FLAGS REQUIRING REPLIT CONFIRMATION

**Flag 1: Optimistic UI pattern for Question objects**
- **What Replit needs to build:** When a WebSocket message arrives with type `OPEN_QUESTION`, the frontend renders the question card immediately on optimistic assumption while the backend database write completes. The card does not wait for database confirmation to render.
- **Action Required:** Replit must confirm this pattern is implemented before Task 2.4 begins.

**Flag 2: Projection-ready state reads**
- **What Replit needs to confirm:** React components currently reading from `inventory_master` and `system_audit_ledger` directly must be confirmed ready to read from projected state tables instead.
- **Action Required:** Replit must confirm which components are affected and their readiness before mutation order inversion begins.

## 2. WEBSOCKET EVENT TYPES
Replit should expect the following footprint structures from Phase 2:
- `OPEN_QUESTION` (new — question object)
- `VERIFICATION_EVENT` (new — assertion closed)
- `CONFLICT_DETECTED` (new — HITL surface)
- `MOUNT_PLATE` (existing — unchanged)
- `greeting` (existing — unchanged)

## 3. NOTIFICATION ONLY
No frontend changes required yet. Replit is being informed, not tasked. Confirmation of the two flags is the only required response at this time.
