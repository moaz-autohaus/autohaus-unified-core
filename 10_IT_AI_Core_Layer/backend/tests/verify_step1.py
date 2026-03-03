
import sys
import os
import asyncio
import json

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from membrane.session_context import SessionContext
from database.bigquery_client import BigQueryClient

async def verify_step1():
    print("=== Phase 3 Step 1 Verification Hook ===")
    
    test_users = [
        {"input_id": "ahsin", "expected_role": "SOVEREIGN", "expected_scope": ["ALL"]},
        {"input_id": "asim", "expected_role": "STANDARD", "expected_scope": ["KAMM_LLC", "AUTOHAUS_SERVICES_LLC"]},
        {"input_id": "mohsin", "expected_role": "STANDARD", "expected_scope": ["ASTROLOGISTICS_LLC", "AUTOHAUS_SERVICES_LLC"]},
        {"input_id": "sunny", "expected_role": "FIELD", "expected_scope": ["FLUIDITRUCK_LLC", "CARLUX_LLC"]},
    ]
    
    from unittest.mock import MagicMock, patch
    mock_bq = MagicMock()
    mock_client = MagicMock()
    mock_bq.client = mock_client
    
    with patch('database.bigquery_client.BigQueryClient', return_value=mock_bq):
        for user_data in test_users:
            user_id = user_data["input_id"]
            print(f"\nVerifying role {user_data['expected_role']} for user {user_id}...")
            
            session = SessionContext.create_session(user_id)
            
            # 1. Assert role and scope match
            assert session.role == user_data["expected_role"], f"Role mismatch for {user_id}: expected {user_data['expected_role']}, got {session.role}"
            assert session.entity_scope == user_data["expected_scope"], f"Scope mismatch for {user_id}: expected {user_data['expected_scope']}, got {session.entity_scope}"
            print(f"✅ Role and scope match for {user_id}")
            
            # 2. Check if SESSION_STARTED was attempted to be logged
            mock_client.insert_rows_json.assert_called()
            last_call_args = mock_client.insert_rows_json.call_args
            rows = last_call_args[0][1]
            assert rows[0]["event_type"] == "SESSION_STARTED"
            assert rows[0]["actor_id"] == user_id
            assert rows[0]["authority"] == user_data["expected_role"]
            print(f"✅ SESSION_STARTED event emission logic verified for {user_id}")
            
            # End session and verify SESSION_ENDED
            session.end_session()
            last_call_args_ended = mock_client.insert_rows_json.call_args
            rows_ended = last_call_args_ended[0][1]
            assert rows_ended[0]["event_type"] == "SESSION_ENDED"
            print(f"✅ SESSION_ENDED event emission logic verified for {user_id}")

    print("\n=== Verification Hook (Logic Only) PASSED ===")

    print("\n=== Verification Hook PASSED ===")

if __name__ == "__main__":
    asyncio.run(verify_step1())
