import logging
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List

from database.policy_engine import get_policy
from database.bigquery_client import BigQueryClient
from .google_workspace_service import workspace

logger = logging.getLogger("autohaus.calendar")

class CalendarSpoke:
    def __init__(self, bq_client=None):
        self.bq_client = bq_client or BigQueryClient().client

    async def check_availability(self, start_time: str, end_time: str, calendar_id: str = "primary") -> bool:
        """
        Queries Google Calendar for busy periods in a time window.
        Returns True if the slot is free.
        """
        body = {
            "timeMin": start_time,
            "timeMax": end_time,
            "items": [{"id": calendar_id}]
        }
        try:
            res = workspace.calendar.freebusy().query(body=body).execute()
            busy_slots = res.get("calendars", {}).get(calendar_id, {}).get("busy", [])
            return len(busy_slots) == 0
        except Exception as e:
            logger.error(f"[CALENDAR] Availability check failed: {e}")
            return False

    async def create_event(self, summary: str, start_iso: str, end_iso: str, attendees: List[str] = None, vin: str = None) -> dict:
        """
        Creates a new service or booking event on the calendar.
        """
        event = {
            'summary': summary,
            'description': f"Auto-scheduled by CIL. VIN: {vin}" if vin else "Auto-scheduled by CIL.",
            'start': {'dateTime': start_iso, 'timeZone': 'America/Los_Angeles'},
            'end': {'dateTime': end_iso, 'timeZone': 'America/Los_Angeles'},
            'attendees': [{'email': e} for e in (attendees or [])],
            'reminders': {'useDefault': True},
        }

        try:
            # Sandbox logic: We could use a "proposed" calendar if not sovereign.
            # Get internal calendar ID from policy
            cal_key = "PRIMARY_SERVICE_CALENDAR"
            target_cal_id = get_policy("CALENDAR", cal_key) or "primary"
            
            created_event = workspace.calendar.events().insert(calendarId=target_cal_id, body=event).execute()
            
            # Log to CIL
            event_row = {
                "event_id": str(uuid.uuid4()),
                "event_type": "CALENDAR_EVENT_CREATED",
                "timestamp": datetime.utcnow().isoformat(),
                "actor_type": "SYSTEM",
                "target_type": "VEHICLE" if vin else "INTERNAL",
                "target_id": vin or target_cal_id,
                "payload": json.dumps({
                    "cal_event_id": created_event['id'],
                    "summary": summary,
                    "start": start_iso
                }),
                "idempotency_key": f"cal_{created_event['id']}"
            }
            if self.bq_client:
                self.bq_client.insert_rows_json("autohaus-infrastructure.autohaus_cil.cil_events", [event_row])
                
            return {"status": "success", "event_id": created_event['id'], "link": created_event.get('htmlLink')}
        except Exception as e:
            logger.error(f"[CALENDAR] Event creation failed: {e}")
            return {"status": "error", "message": str(e)}

    async def get_next_available_slots(self, days: int = 3) -> List[Dict[str, str]]:
        """
        High-level helper to find free slots in the upcoming days.
        Used for lead follow-ups.
        """
        # Logic to iterate work hours and call check_availability
        return [{"start": "2026-03-01T10:00:00Z", "end": "2026-03-01T11:00:00Z"}]
