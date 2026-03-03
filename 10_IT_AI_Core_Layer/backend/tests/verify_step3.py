
import sys
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from membrane.session_context import SessionContext
from membrane.channel_selector import ChannelSelector

def verify_step3():
    print("=== Phase 3 Step 3 Verification Hook ===")
    
    mock_bq = MagicMock()
    mock_client = MagicMock()
    mock_bq.client = mock_client
    
    with patch('database.bigquery_client.BigQueryClient', return_value=mock_bq):
        # 1. Active Session
        session = SessionContext.create_session("ahsin")
        session.last_activity_at = datetime.now(timezone.utc)
        
        selector = ChannelSelector()
        
        print("\nTest 1: Active session, high priority conflict...")
        selection1 = selector.decide_channels(session, "MATERIAL_CONFLICT_DETECTED", "HIGH")
        assert "WS" in selection1.channels, "Expected WS in channels for active session"
        assert "SMS" in selection1.channels, "Expected SMS for critical conflict"
        print(f"✅ Channels: {selection1.channels} (Reason: {selection1.reason})")
        
        # 2. Inactive Session
        print("\nTest 2: Inactive session, high priority conflict...")
        session.last_activity_at = datetime.now(timezone.utc) - timedelta(seconds=60)
        selection2 = selector.decide_channels(session, "MATERIAL_CONFLICT_DETECTED", "HIGH")
        assert "SMS" in selection2.channels, "Expected SMS for high priority inactive"
        assert "WS" not in selection2.channels, "Did not expect WS for inactive session"
        print(f"✅ Channels: {selection2.channels} (Reason: {selection2.reason})")
        
        # 3. Active Session, Normal Priority
        print("\nTest 3: Active session, normal priority event...")
        session.last_activity_at = datetime.now(timezone.utc)
        selection3 = selector.decide_channels(session, "NEW_LEAD", "NORMAL")
        assert selection3.channels == ["WS"], f"Expected only WS for active normal, got {selection3.channels}"
        print(f"✅ Channels: {selection3.channels}")

        # 4. Inactive Session, Normal Priority
        print("\nTest 4: Inactive session, normal priority event...")
        session.last_activity_at = datetime.now(timezone.utc) - timedelta(seconds=60)
        selection4 = selector.decide_channels(session, "NEW_LEAD", "NORMAL")
        assert selection4.channels == ["QUEUE"], f"Expected QUEUE for inactive normal, got {selection4.channels}"
        print(f"✅ Channels: {selection4.channels}")

    print("\n=== Verification Hook PASSED ===")

if __name__ == "__main__":
    verify_step3()
