import time
import datetime
from google.cloud import bigquery
from utils.audit_watcher import AuditWatcher

class TimerService:
    def __init__(self, project_id="autohaus-infrastructure"):
        self.project_id = project_id
        self.client = bigquery.Client(project=project_id)

    def pulse(self, audit_context: dict):
        """
        Monitor BigQuery intake_log and calculate ingestion delta.
        """
        AuditWatcher.verify_context(audit_context)
        
        print(f"[PULSE] Initiating 60-Minute Cycle | RunID: {audit_context['run_id']}")
        
        query = f"""
            SELECT ingestion_time, draft_completion_time 
            FROM `{self.project_id}.inventory.intake_log`
            ORDER BY ingestion_time DESC
            LIMIT 10
        """
        try:
            query_job = self.client.query(query)
            results = query_job.result()
            
            for row in results:
                if row.ingestion_time and row.draft_completion_time:
                    delta = row.draft_completion_time - row.ingestion_time
                    print(f"[PULSE] VIN Sync Delta: {delta} | Status: Observed")
        except Exception as e:
            print(f"[PULSE] Registry Access Anomaly: {str(e)}")

    def run_cycle(self):
        """Service loop for the 60-minute interval."""
        while True:
            context = {
                "run_id": AuditWatcher.generate_id(),
                "operator_id": "moaz@autohausia.com",
                "timestamp": str(datetime.datetime.now())
            }
            self.pulse(context)
            time.sleep(3600)  # 60 Minute Pulse
