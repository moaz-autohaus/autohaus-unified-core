# CIL Meta-Layer Contract

This document defines the `/api/security/` contract for when the Meta-Layer is initiated. These are strictly predefined signatures for Sovereign and Meta-Layer access. They are NOT built yet, but defined here for Phase 2 architectural alignment.

## Tool Signatures

### 1. `get_business_health()`
- **Purpose**: Provides a macro-level overview of the entire entity's health across all CIL subsystems.
- **Returns**: 
  - `anomaly_status`: Current state of the anomaly detection engine (e.g., NORMAL, ELEVATED, CRITICAL).
  - `cash_position`: Current total cash position aggregated from the financial ledger.
  - `open_question_count`: Total number of unresolved questions requiring human or sovereign review.
  - `days_since_last_governance_review`: Time elapsed since the last sovereign-level systemic review.

### 2. `get_inventory_summary()`
- **Purpose**: Provides the macro-level fleet status across all unified entities.
- **Returns**: 
  - `fleet_status`: Aggregated counts of vehicles in Pending, Active, Sold, or Exception states across all physical and logical locations.

### 3. `trigger_governance_review()`
- **Purpose**: Surfaces all pending proposals that require high-tier authorization.
- **Returns**: 
  - An array of `SOVEREIGN` tier approval proposals that are currently blocked in the HITL queue.

### 4. `kill_switch(reason)`
- **Purpose**: Hard stop mechanism for the entire autonomous pipeline.
- **Parameters**: 
  - `reason` (string): Justification or code for initiating the kill switch.
- **Constraints / Actions**:
  - Halts all system execution and writes `HARD_STOP_ENFORCED` to the `cil_events` table.
  - **Requires**: `SOVEREIGN` token validation. 
  - Cannot be executed by standard service accounts or external webhooks.
