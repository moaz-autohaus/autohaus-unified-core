
import logging
import uuid
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

# Setup logger
logger = logging.getLogger("autohaus.membrane.translation_engine")

class UIPlatePayload(BaseModel):
    """Payload optimized for JIT UI rendering (MOUNT_PLATE)."""
    plate_id: str
    plate_type: str        # CONFLICT_PLATE | LEAD_PLATE | FACT_PLATE | ERROR_MODAL
    target_entity_id: str
    display_title: str
    display_data: Dict[str, Any]
    available_actions: List[Dict[str, str]] # [{'label': 'Resolve', 'action': 'RESOLVE_CONFLICT'}]
    severity: str          # INFO | WARNING | CRITICAL
    timestamp: str

class TranslationEngine:
    """
    Decoupling layer between the CIL operational spine and the React JIT UI.
    Converts internal event structures into 'Plates' that can be mounted in the UI.
    """
    
    def translate_to_plate(self, event_type: str, payload: Dict[str, Any]) -> Optional[UIPlatePayload]:
        """
        Maps internal CIL event types and payloads to UI-optimized Plate structures.
        """
        import datetime
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        logger.debug(f"[TRANSLATION] Translating {event_type} to UI Plate")

        if event_type == "CONFLICT_DETECTED":
            return self._to_conflict_plate(payload, timestamp)
            
        elif event_type == "NEW_LEAD":
            return self._to_lead_plate(payload, timestamp)
            
        elif event_type == "HARD_STOP_ENFORCED":
            return self._to_error_modal(payload, timestamp)

        elif event_type == "ENRICHMENT_PROPOSED":
            return self._to_gate_modal(payload, timestamp)
            
        # Default: ignore events that don't need a UI representation
        return None

    def _to_conflict_plate(self, payload: Dict[str, Any], timestamp: str) -> UIPlatePayload:
        return UIPlatePayload(
            plate_id=f"plate_{str(uuid.uuid4())[:8]}",
            plate_type="CONFLICT_PLATE",
            target_entity_id=payload.get("target_id", "UNKNOWN"),
            display_title="⚠️ Data Integrity Conflict",
            display_data={
                "message": "A new claim contradicts an existing verified fact.",
                "variance": payload.get("variance_description", "Mismatched values outside tolerance"),
                "existing": payload.get("existing_value"),
                "proposed": payload.get("extracted_value")
            },
            available_actions=[
                {"label": "Verify New Data", "action": "RESOLVE_CONFLICT_ACCEPT"},
                {"label": "Keep Existing", "action": "RESOLVE_CONFLICT_REJECT"},
                {"label": "Ask Origin", "action": "CREATE_OPEN_QUESTION"}
            ],
            severity="CRITICAL",
            timestamp=timestamp
        )

    def _to_lead_plate(self, payload: Dict[str, Any], timestamp: str) -> UIPlatePayload:
        return UIPlatePayload(
            plate_id=f"plate_{str(uuid.uuid4())[:8]}",
            plate_type="LEAD_PLATE",
            target_entity_id=payload.get("person_id", "NEW"),
            display_title="✨ New Active Lead",
            display_data={
                "name": payload.get("name", "Unknown Lead"),
                "source": payload.get("source", "Omnichannel Inbox"),
                "interest": payload.get("interest_summary", "Generic Inquiry"),
                "contact": payload.get("contact_method")
            },
            available_actions=[
                {"label": "View Details", "action": "VIEW_PERSON"},
                {"label": "Assign to Sales", "action": "ASSIGN_LEAD"}
            ],
            severity="INFO",
            timestamp=timestamp
        )

    def _to_error_modal(self, payload: Dict[str, Any], timestamp: str) -> UIPlatePayload:
        return UIPlatePayload(
            plate_id=f"plate_{str(uuid.uuid4())[:8]}",
            plate_type="ERROR_MODAL",
            target_entity_id=payload.get("target_id", "SYSTEM"),
            display_title="🛑 Operation Blocked",
            display_data={
                "reason": payload.get("reason", "Access denied by CIL policy."),
                "action_attempted": payload.get("action_attempted"),
                "reconciliation": "Contact CEO for SOVEREIGN override or resolve underlying conflict."
            },
            available_actions=[
                {"label": "Acknowledge", "action": "DISMISS_PLATE"}
            ],
            severity="CRITICAL",
            timestamp=timestamp
        )

    def _to_gate_modal(self, payload: Dict[str, Any], timestamp: str) -> UIPlatePayload:
        return UIPlatePayload(
            plate_id=f"plate_{str(uuid.uuid4())[:8]}",
            plate_type="APPROVAL_GATE",
            target_entity_id=payload.get("target_id", "SYSTEM"),
            display_title="🔐 Approval Required",
            display_data={
                "reason": payload.get("reason", "Action requires higher authority."),
                "action_attempted": payload.get("action_attempted"),
                "gate_id": payload.get("block_id")
            },
            available_actions=[
                {"label": "Request Approval", "action": "SUBMIT_GATE_REQUEST"},
                {"label": "Cancel", "action": "DISMISS_PLATE"}
            ],
            severity="WARNING",
            timestamp=timestamp
        )
