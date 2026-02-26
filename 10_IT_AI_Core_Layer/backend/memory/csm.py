import sqlite3
import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

logger = logging.getLogger("autohaus.csm")

CSM_DB_PATH = os.path.join(os.path.dirname(__file__), "csm.db")

class ConversationStateManager:
    """
    The Conversation State Manager (CSM).
    Acts as the 'waiting room' for the Intelligent Membrane.
    If a human input is incomplete (e.g. missing a VIN), the CSM stores the current
    state of the interaction here. When the user replies, the state is rehydrated.
    """

    def __init__(self, db_path: str = CSM_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_conversations (
                    user_id TEXT PRIMARY KEY,
                    session_state TEXT NOT NULL,
                    pending_intent TEXT NOT NULL,
                    collected_entities TEXT NOT NULL,
                    last_updated TIMESTAMP NOT NULL
                )
            """)
            conn.commit()

    def get_state(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve active pending state for a user (e.g., their phone number)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT session_state, pending_intent, collected_entities, last_updated FROM active_conversations WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                "session_state": row[0],
                "pending_intent": row[1],
                "collected_entities": json.loads(row[2]),
                "last_updated": row[3]
            }

    def set_state(self, user_id: str, session_state: str, pending_intent: str, collected_entities: dict):
        """Save an incomplete interaction state so the Membrane can ask follow-up questions."""
        timestamp = datetime.now(timezone.utc).isoformat()
        entities_json = json.dumps(collected_entities)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO active_conversations (user_id, session_state, pending_intent, collected_entities, last_updated)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    session_state=excluded.session_state,
                    pending_intent=excluded.pending_intent,
                    collected_entities=excluded.collected_entities,
                    last_updated=excluded.last_updated
            """, (user_id, session_state, pending_intent, entities_json, timestamp))
            conn.commit()
            logger.info(f"CSM updated for User [{user_id}]: State={session_state}, Intent={pending_intent}")

    def clear_state(self, user_id: str):
        """Remove state when an interaction is successfully completed."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM active_conversations WHERE user_id = ?", (user_id,))
            conn.commit()
            logger.info(f"CSM state cleared for User [{user_id}]")

if __name__ == "__main__":
    csm = ConversationStateManager()
    # Test setting state
    csm.set_state("+15555555555", "PENDING_VIN", "INVENTORY", {"action": "upload_photo", "confidence": 0.9})
    print(csm.get_state("+15555555555"))
    csm.clear_state("+15555555555")
