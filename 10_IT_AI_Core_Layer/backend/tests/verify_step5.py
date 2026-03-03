
import sys
import os
import asyncio
import json
from unittest.mock import MagicMock, AsyncMock, patch

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from membrane.ws_router import WebSocketRouter

async def verify_step5():
    print("=== Phase 3 Step 5 Verification Hook ===")
    
    router = WebSocketRouter()
    
    # 1. Simulate Connection
    mock_ws = AsyncMock()
    user_id = "ahsin"
    
    print("\nTest: Simulating WebSocket connection for ahsin...")
    
    # Use a task to handle the connection loop which will block
    # We patch SessionContext.create_session to return a mock or just let it run
    # since we already tested Step 1.
    
    mock_bq = MagicMock()
    mock_client = MagicMock()
    mock_bq.client = mock_client
    
    with patch('database.bigquery_client.BigQueryClient', return_value=mock_bq):
        # We need to manually trigger the part of 'handle_connection' that sets up the registry
        # Or better, we just manually populate the registry for testing 'route_cil_event'
        from membrane.session_context import SessionContext
        session = SessionContext.create_session(user_id)
        from membrane.ws_router import active_sessions, active_connections
        active_sessions[session.session_id] = session
        active_connections[session.session_id] = mock_ws
        
        print(f"Session {session.session_id} registered.")

        # 2. Simulate CIL Event from Spine
        print("\nTest: Routing CIL event 'MATERIAL_CONFLICT_DETECTED'...")
        cil_event = {
            "event_type": "MATERIAL_CONFLICT_DETECTED",
            "entity_id": "VEH_9923",
            "payload": json.dumps({
                "target_id": "VEH_9923",
                "existing_value": "$45,000",
                "extracted_value": "$48,000",
                "variance_description": "Price mismatch"
            })
        }
        
        await router.route_cil_event(cil_event)
        
        # 3. Assert correct message pushed to socket
        mock_ws.send_json.assert_called()
        last_msg = mock_ws.send_json.call_args[0][0]
        
        assert last_msg["type"] == "MOUNT_PLATE"
        assert last_msg["data"]["plate_type"] == "CONFLICT_PLATE"
        assert last_msg["data"]["display_data"]["existing"] == "$45,000"
        print(f"✅ MOUNT_PLATE with correct translation pushed to WebSocket.")

    print("\n=== Verification Hook PASSED ===")

if __name__ == "__main__":
    asyncio.run(verify_step5())
