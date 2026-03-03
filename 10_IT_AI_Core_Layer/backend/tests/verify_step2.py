
import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from membrane.session_context import SessionContext
from membrane.policy_enforcer import PolicyEnforcer

async def verify_step2():
    print("=== Phase 3 Step 2 Verification Hook ===")
    
    mock_bq = MagicMock()
    mock_client = MagicMock()
    mock_bq.client = mock_client
    
    # Mocking BQ result for blocks (initially empty)
    mock_client.query.return_value.result.return_value = []
    
    with patch('database.bigquery_client.BigQueryClient', return_value=mock_bq):
        # 1. Setup session as STANDARD (Asim)
        session_asim = SessionContext.create_session("asim")
        enforcer = PolicyEnforcer(bq_client=mock_bq)
        
        print("\nTest 1: FORCE_APPLY_FIELD as STANDARD...")
        outcome1 = await enforcer.enforce_action(session_asim, "FORCE_APPLY_FIELD", "KAMM_LLC")
        assert outcome1.status == "GATE", f"Expected GATE for standard force apply, got {outcome1.status}"
        print(f"✅ Outcome: {outcome1.status} (Reason: {outcome1.reason})")
        
        # Verify event emission logic
        mock_client.insert_rows_json.assert_called()
        last_call = mock_client.insert_rows_json.call_args
        rows = last_call[0][1]
        assert rows[0]["event_type"] == "ENFORCEMENT_GATE"
        print(f"✅ ENFORCEMENT_GATE event emission logic verified")
        
        # 2. Setup session as FIELD (Sunny)
        session_sunny = SessionContext.create_session("sunny")
        
        print("\nTest 2: POLICY_WRITE as FIELD...")
        outcome2 = await enforcer.enforce_action(session_sunny, "POLICY_WRITE", "CARBON_LLC")
        assert outcome2.status == "STOP", f"Expected STOP for field policy write, got {outcome2.status}"
        print(f"✅ Outcome: {outcome2.status} (Reason: {outcome2.reason})")

        # Verify event emission logic
        last_call = mock_client.insert_rows_json.call_args
        rows = last_call[0][1]
        assert rows[0]["event_type"] == "ENFORCEMENT_STOP"
        print(f"✅ ENFORCEMENT_STOP event emission logic verified")
        
        # 3. Test entity scope violation
        print("\nTest 3: Action on entity OUTSIDE scope...")
        # Sunny is scoped to FLUIDITRUCK_LLC, CARLUX_LLC. KAMM_LLC is outside.
        outcome3 = await enforcer.enforce_action(session_sunny, "VIEW_PLATE", "KAMM_LLC")
        assert outcome3.status == "STOP"
        assert "outside the authorized scope" in outcome3.reason
        print(f"✅ Outcome: {outcome3.status} (Scope Violation verified)")

        # 4. Test HARD STOP from BQ
        print("\nTest 4: HARD STOP from CIL projections...")
        # Mocking an active conflict
        mock_row = MagicMock()
        mock_row.type = "CONFLICT"
        mock_row.block_id = "conf_123"
        mock_row.reason = "VIN mismatch on invoice"
        mock_client.query.return_value.result.return_value = [mock_row]
        
        # Standard user (Asim) tries to view the conflicted entity
        outcome4 = await enforcer.enforce_action(session_asim, "VIEW_PLATE", "KAMM_LLC")
        assert outcome4.status == "STOP"
        assert "Active HARD STOP" in outcome4.reason
        print(f"✅ Outcome: {outcome4.status} (Hard Stop logic verified)")

    print("\n=== Verification Hook PASSED ===")

if __name__ == "__main__":
    asyncio.run(verify_step2())
