
import uuid
import json
import logging
import os
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# Setup logger
logger = logging.getLogger("autohaus.membrane.session_context")

class SessionContext(BaseModel):
    """
    Track who is active, what role they hold, what entity scope they can see,
    and what has happened in this session. Ephemeral membrane memory.
    """
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    role: str                 # SOVEREIGN | STANDARD | FIELD
    entity_scope: List[str] = []
    active_entity: Optional[str] = None
    session_started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pending_approvals: List[str] = []   # action_ids awaiting this user's approval
    active_hard_stops: List[str] = []   # policy breach ids currently blocking actions

    @classmethod
    def create_session(cls, user_id: str) -> "SessionContext":
        """
        Creates a new SessionContext on every WebSocket connection.
        Reads entity scope and role from business_ontology.json.
        """
        # Normalize user_id to match ontology keys (e.g., 'AHSIN_CEO' -> 'ahsin')
        user_id_clean = user_id.lower().split('_')[0]
        
        ontology_path = os.path.join(os.path.dirname(__file__), '..', 'registry', 'business_ontology.json')
        role = "FIELD"
        scope = []
        
        try:
            if os.path.exists(ontology_path):
                with open(ontology_path, 'r') as f:
                    ontology = json.load(f)
                
                matrix = ontology.get("personnel_access_matrix", {})
                user_data = matrix.get(user_id_clean)
                
                if user_data:
                    role = user_data.get("role", "FIELD")
                    scope = user_data.get("scope", [])
                    if scope == "ALL":
                        # In enforcement logic, "ALL" means no restriction.
                        # We keep it as ["ALL"] or expand it. Brief says "all entities".
                        # We'll leave it as ["ALL"] for logic check.
                        scope = ["ALL"]
                else:
                    logger.warning(f"[SESSION] User '{user_id}' ('{user_id_clean}') not found in personnel_access_matrix. Defaulting to FIELD role.")
            else:
                logger.error(f"[SESSION] business_ontology.json not found at {ontology_path}")
        except Exception as e:
            logger.error(f"[SESSION] Failed to load entity scope for {user_id}: {e}")

        session = cls(
            user_id=user_id,
            role=role,
            entity_scope=scope if isinstance(scope, list) else [scope],
            active_entity=scope[0] if isinstance(scope, list) and scope and scope[0] != "ALL" else None
        )
        
        # DO emit SESSION_STARTED event to cil_events
        session.emit_event("SESSION_STARTED")
        logger.info(f"[SESSION] Created session {session.session_id} for user {user_id} with role {role}")
        
        return session

    def update_activity(self):
        """Updates the last activity timestamp."""
        self.last_activity_at = datetime.now(timezone.utc)

    def end_session(self):
        """
        Called on WebSocket disconnect.
        DO emit SESSION_ENDED event to cil_events.
        """
        self.emit_event("SESSION_ENDED")
        logger.info(f"[SESSION] Ended session {self.session_id} for user {self.user_id}")

    def emit_event(self, event_type: str, payload: Optional[Dict[str, Any]] = None):
        """
        Emits a durable event to the cil_events spine (BigQuery).
        Follows the canonical event schema from Section 1 of CLAIMS_AND_EVENTS_CANON.md.
        """
        from database.bigquery_client import BigQueryClient
        bq = BigQueryClient()
        
        event_id = str(uuid.uuid4())
        event_row = {
            "event_id": event_id,
            "event_type": event_type,
            "entity_id": self.user_id,
            "entity_type": "PERSON",
            "session_id": self.session_id,
            "actor_id": self.user_id,
            "correlation_id": None,
            "parent_event_id": None,
            "emitted_by": "membrane.session_context",
            "authority": self.role,
            "payload": json.dumps(payload or {
                "user_id": self.user_id,
                "role": self.role,
                "entity_scope": self.entity_scope,
                "session_started_at": self.session_started_at.isoformat()
            }),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        if not bq.client:
            logger.warning(f"[SESSION] Skipping BQ emit for {event_type} (Client unavailable)")
            return

        try:
            table_id = "autohaus-infrastructure.autohaus_cil.cil_events"
            errors = bq.client.insert_rows_json(table_id, [event_row])
            if errors:
                logger.error(f"[SESSION] BQ insert failed for {event_type}: {errors}")
        except Exception as e:
            logger.error(f"[SESSION] Exception emitting {event_type}: {e}")

    def is_in_scope(self, entity_id: str) -> bool:
        """Checks if a given entity is within the user's authorized scope."""
        if "ALL" in self.entity_scope:
            return True
        return entity_id in self.entity_scope
