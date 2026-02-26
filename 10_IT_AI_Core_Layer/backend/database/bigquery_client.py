import json
import os
import uuid
import logging
from google.cloud import bigquery
from google.oauth2 import service_account
from ..models.events import CILEvent

logger = logging.getLogger(__name__)

class BigQueryClient:
    def __init__(self):
        self.project_id = "autohaus-infrastructure"
        self.dataset_id = "autohaus_cil"
        # In Replit, this is set. Locally, we might need a fallback.
        sa_json_str = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
        
        if sa_json_str:
            try:
                # We expect raw JSON string in the environment variable.
                sa_info = json.loads(sa_json_str)
                self.credentials = service_account.Credentials.from_service_account_info(sa_info)
                self.client = bigquery.Client(credentials=self.credentials, project=self.project_id)
            except Exception as e:
                logger.error(f"Failed to parse GCP_SERVICE_ACCOUNT_JSON or init client: {str(e)}")
                self.client = None
        else:
            # Fallback for local development if the environment variable isn't set
            local_key_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "auth", "replit-sa-key.json")
            if os.path.exists(local_key_path):
                self.credentials = service_account.Credentials.from_service_account_file(local_key_path)
                self.client = bigquery.Client(credentials=self.credentials, project=self.project_id)
            else:
                logger.warning("No GCP_SERVICE_ACCOUNT_JSON in env and no local fallback found. BigQuery client will use default credentials.")
                self.client = bigquery.Client(project=self.project_id)

    def execute_query(self, query: str, parameters: list = None):
        """Execute a general query (DDL or DML)."""
        if not self.client:
            raise Exception("BigQuery client not initialized.")
            
        job_config = bigquery.QueryJobConfig()
        if parameters:
            job_config.query_parameters = parameters
            
        query_job = self.client.query(query, job_config=job_config)
        return query_job.result()
        
    def _is_idempotency_key_used(self, idempotency_key: str) -> bool:
        if not idempotency_key:
            return False
            
        query = f"""
            SELECT event_id 
            FROM `{self.project_id}.{self.dataset_id}.cil_events` 
            WHERE idempotency_key = @idempotency_key 
            LIMIT 1
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("idempotency_key", "STRING", idempotency_key)
            ]
        )
        try:
            results = list(self.client.query(query, job_config=job_config).result())
            return len(results) > 0
        except Exception as e:
            logger.error(f"Error checking idempotency: {e}")
            # If the table doesn't exist yet, we allow it.
            return False

    def insert_cil_event(self, event: CILEvent) -> bool:
        """Insert a CIL event into the single audit spine with idempotency check."""
        if not self.client:
            logger.error("BigQuery client not initialized. Cannot insert event.")
            return False

        # 1. Enforce Event Payload Shape Compliance before inserting
        try:
            CILEvent.validate_payload(event.event_type, event.payload)
        except Exception as e:
            logger.error(f"Event payload validation failed for {event.event_type}: {e}")
            raise

        # 2. Idempotency Check
        if event.idempotency_key and self._is_idempotency_key_used(event.idempotency_key):
            logger.info(f"Event with idempotency_key {event.idempotency_key} already exists. Skipping insertion.")
            return True # Technically a success since it's already there

        # 3. Prepare the row
        table_ref = f"{self.project_id}.{self.dataset_id}.cil_events"
        row_to_insert = {
            "event_id": event.event_id or str(uuid.uuid4()),
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "actor_type": event.actor_type.value,
            "actor_id": event.actor_id,
            "actor_role": event.actor_role.value if event.actor_role else None,
            "target_type": event.target_type.value,
            "target_id": event.target_id,
            "payload": json.dumps(event.payload),
            "metadata": json.dumps(event.metadata.dict(exclude_none=True)) if event.metadata else None,
            "idempotency_key": event.idempotency_key
        }

        # 4. Stream Insert (or can use Load Job, but streming is better for single events)
        errors = self.client.insert_rows_json(table_ref, [row_to_insert])
        
        if errors:
            logger.error(f"Encountered errors while inserting rows: {errors}")
            return False
            
        logger.info(f"Successfully inserted event {row_to_insert['event_id']} of type {row_to_insert['event_type']}")
        return True

# Simple test/initialization
# bq_client = BigQueryClient()
