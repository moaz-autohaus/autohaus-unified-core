from google.cloud import bigquery
import json

client = bigquery.Client()

def print_claims(proposal_id):
    query = f"SELECT payload FROM `autohaus-infrastructure.autohaus_cil.hitl_events` WHERE hitl_event_id = '{proposal_id}'"
    try:
        results = list(client.query(query).result())
        for row in results:
            payload = json.loads(row.payload)
            for action in payload.get('actions', []):
                if action.get('type') == 'APPLY_CLAIMS':
                    claims = action.get('params', {}).get('claims', [])
                    print(f"Claims count: {len(claims)}")
                    for c in claims:
                        target = c.get('target_field')
                        val = c.get('extracted_value')
                        print(f"  {target} -> {repr(val)[:60]}")
                    return
    except Exception as e:
        print(f"Error printing claims: {e}")

print("--- Checking newest PROPOSED claims ---")
query_latest = "SELECT hitl_event_id, status FROM `autohaus-infrastructure.autohaus_cil.hitl_events` WHERE status = 'PROPOSED' ORDER BY created_at DESC LIMIT 1"
latest_res = list(client.query(query_latest).result())
if latest_res:
    pid = latest_res[0].hitl_event_id
    print(f"ID: {pid}, Status: {latest_res[0].status}")
    print_claims(pid)
else:
    print("No PROPOSED proposal found")

print("\n--- Checking latest OPEN_QUESTION_CREATED event ---")
query_events = "SELECT * FROM `autohaus-infrastructure.autohaus_cil.cil_events` WHERE event_type = 'OPEN_QUESTION_CREATED' ORDER BY created_at DESC LIMIT 1"
try:
    events = list(client.query(query_events).result())
    for e in events:
        print(f"{e.created_at}: {e.event_type} - {json.dumps(dict(e.items()), default=str)}")
except Exception as ex:
    print("Failed to query cil_events table:", ex)

print("\n--- Checking open questions ---")
query_questions = "SELECT * FROM `autohaus-infrastructure.autohaus_cil.open_questions` ORDER BY created_at DESC LIMIT 1"
try:
    questions = list(client.query(query_questions).result())
    for q in questions:
        print(json.dumps(dict(q.items()), default=str))
except Exception as e:
    print("could not find open_questions:", e)
