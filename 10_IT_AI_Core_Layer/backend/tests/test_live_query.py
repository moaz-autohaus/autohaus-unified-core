
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.bigquery_client import BigQueryClient

def test_live_query():
    print("Testing live BigQuery connection...")
    bq = BigQueryClient()
    if not bq.client:
        print("❌ BigQuery Client could not be initialized.")
        return

    query = """
    SELECT event_type, entity_id, created_at, emitted_by
    FROM `autohaus-infrastructure.autohaus_cil.cil_events`
    WHERE event_type IN ('SESSION_STARTED', 'SESSION_ENDED', 'HARD_STOP_ENFORCED', 'HARD_STOP_OVERRIDDEN')
    ORDER BY created_at DESC
    LIMIT 10
    """
    
    try:
        results = list(bq.client.query(query).result())
        print(f"✅ Query successful. Found {len(results)} rows.")
        for row in results:
            print(f"Type: {row.event_type} | ID: {row.entity_id} | Time: {row.created_at} | By: {row.emitted_by}")
    except Exception as e:
        print(f"❌ Query failed: {e}")

if __name__ == "__main__":
    test_live_query()
