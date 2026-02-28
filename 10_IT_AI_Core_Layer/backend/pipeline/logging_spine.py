import logging
import uuid
from datetime import datetime

logger = logging.getLogger("autohaus.logging_spine")


def log_cil_event(bq_client=None, event_type="UNKNOWN", source="SYSTEM", entity_id=None, payload=None, **kwargs):
    logger.info(f"[CIL EVENT] {event_type} from {source} | entity={entity_id} | payload={payload}")
    if bq_client:
        try:
            import json
            row = {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "actor_type": "SYSTEM",
                "actor_id": source,
                "actor_role": "SYSTEM",
                "target_type": kwargs.get("target_type", "UNKNOWN"),
                "target_id": entity_id or "UNKNOWN",
                "payload": json.dumps(payload) if payload else None,
                "metadata": None,
                "idempotency_key": f"spine_{event_type}_{uuid.uuid4().hex[:8]}",
            }
            bq_client.insert_rows_json(
                "autohaus-infrastructure.autohaus_cil.cil_events", [row]
            )
        except Exception as e:
            logger.error(f"[CIL EVENT] Failed to write to BigQuery: {e}")
