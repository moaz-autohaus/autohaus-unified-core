
import sys
import os
import uuid
from datetime import datetime, timezone
import logging

# Setup basic logging to see the output from the classes
logging.basicConfig(level=logging.INFO)

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from membrane.session_context import SessionContext

def test_session_emission():
    print("Testing session event emission to live BigQuery...")
    user_id = "AHSIN_CEO"
    try:
        session = SessionContext.create_session(user_id)
        print(f"✅ Session created: {session.session_id}")
        
        session.end_session()
        print("✅ Session ended.")
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")

if __name__ == "__main__":
    test_session_emission()
