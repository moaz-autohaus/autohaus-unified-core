"""
AutoHaus CIL — Native Governance Correction Feedback Loop (Pass 7)
"""

import json
import logging
import uuid
from datetime import datetime

logger = logging.getLogger("autohaus.feedback_loop")

def process_correction_event(bq_client, field_name: str, old_value: str, new_value: str, actor_id: str, document_id: str):
    """
    Called when a human overrides a system extraction.
    Creates a CORRECTION_APPLIED event and potentially flags the extractor for review.
    """
    
    logger.info(f"[FEEDBACK] Correction on {field_name}: '{old_value}' -> '{new_value}' by {actor_id}")
    
    now = datetime.utcnow().isoformat()
    feedback_id = str(uuid.uuid4())
    
    # We could insert into a `corrections` table, or just use cil_events as the spine.
    # The blueprint states "Corrections produce policy/registry improvements over time."
    # we emit a high-signal CORRECTION_APPLIED event.
    
    correction_event = {
        "event_id": feedback_id,
        "event_type": "CORRECTION_APPLIED",
        "timestamp": now,
        "actor_type": "HUMAN",
        "actor_id": actor_id,
        "actor_role": "STANDARD",
        "target_type": "DOCUMENT",
        "target_id": document_id,
        "payload": json.dumps({
            "field_name": field_name,
            "system_value": old_value,
            "human_value": new_value,
            "requires_prompt_tuning": True, # A signal for AI telemetry
        }),
        "metadata": None,
        "idempotency_key": f"corr_{document_id}_{field_name}_{now}"
    }
    
    try:
        errs = bq_client.insert_rows_json("autohaus-infrastructure.autohaus_cil.cil_events", [correction_event])
        if errs:
            logger.error(f"[FEEDBACK] Failed to insert correction event: {errs}")
    except Exception as e:
        logger.error(f"[FEEDBACK] Error processing correction: {e}")
