"""
AutoHaus CIL — Native Governance Escalation Worker (Pass 7)

D5: Open Questions Ops Loop
Periodically scans for OPEN/SNOOZED questions that have breached SLAs,
escalates their status, and fires Twilio notifications.
"""

import os
import time
import logging
from datetime import datetime, timezone
from google.cloud import bigquery

# Hacky relative import for scripts dir if needed, or structured differently
try:
    from backend.database.policy_engine import get_policy
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from database.policy_engine import get_policy

logger = logging.getLogger("autohaus.escalation")
logging.basicConfig(level=logging.INFO)

def get_bq_client():
    from google.oauth2 import service_account
    import json
    project_id = "autohaus-infrastructure"
    sa_json_str = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    if sa_json_str:
        sa_info = json.loads(sa_json_str)
        credentials = service_account.Credentials.from_service_account_info(sa_info)
        return bigquery.Client(credentials=credentials, project=project_id)
            
    local_key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "auth", "replit-sa-key.json")
    if os.path.exists(local_key_path):
        credentials = service_account.Credentials.from_service_account_file(local_key_path)
        return bigquery.Client(credentials=credentials, project=project_id)
    return None

def send_escalation_sms(question_type, description):
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_num = os.environ.get("TWILIO_PHONE_NUMBER")
    to_num = os.environ.get("CEO_PHONE_NUMBER")

    if not all([account_sid, auth_token, from_num, to_num]):
        logger.warning("[ESCALATION] Missing Twilio credentials. Skipping SMS.")
        return

    from twilio.rest import Client
    client = Client(account_sid, auth_token)
    try:
        client.messages.create(
            body=f"🚨 [CIL ESCALATION] Open Question ({question_type}) breached SLA:\n{description[:100]}...",
            from_=from_num,
            to=to_num
        )
    except Exception as e:
        logger.error(f"[ESCALATION] Twilio SMS failed: {e}")

def run_escalation_scan():
    client = get_bq_client()
    if not client:
        return

    # default fallback is 24 hours
    sla_hours = float(get_policy("ESCALATION", "max_overdue_hours") or 24.0)

    query = f"""
        SELECT question_id, question_type, priority, description, created_at, snoozed_until 
        FROM `autohaus-infrastructure.autohaus_cil.open_questions`
        WHERE status = 'OPEN' 
        AND (
            snoozed_until IS NULL AND TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), created_at, HOUR) > {sla_hours}
            OR 
            snoozed_until < CURRENT_TIMESTAMP()
        )
    """
    
    try:
        results = list(client.query(query).result())
        for row in results:
            # Escalate
            update_q = """
                UPDATE `autohaus-infrastructure.autohaus_cil.open_questions`
                SET status = 'ESCALATED' 
                WHERE question_id = @qid
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("qid", "STRING", row.question_id)]
            )
            client.query(update_q, job_config=job_config).result()
            
            logger.info(f"[ESCALATION] Escalating QID: {row.question_id}")
            send_escalation_sms(row.question_type, row.description)
            
    except Exception as e:
        logger.error(f"[ESCALATION] Scan failed: {e}")

if __name__ == "__main__":
    while True:
        run_escalation_scan()
        time.sleep(3600) # Check every hour
