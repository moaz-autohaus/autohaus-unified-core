import os
import logging
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from google.cloud import secretmanager
from google.cloud import run_v2
from google.cloud import bigquery
from google.protobuf import field_mask_pb2
from twilio.rest import Client as TwilioClient

from database.bigquery_client import BigQueryClient
from models.events import CILEvent, EventType, ActorType, ActorRole, TargetType

logger = logging.getLogger("autohaus.rotation_utils")

PROJECT_ID = "autohaus-infrastructure"
REGION = "us-central1"
SERVICE_NAME = "autohaus-cil"
BQ_DATASET = "autohaus_cil"

def get_secret_manager_client():
    """Returns an authenticated Secret Manager client."""
    return secretmanager.SecretManagerServiceClient()

def get_cloud_run_client():
    """Returns an authenticated Cloud Run Admin client."""
    return run_v2.ServicesClient()

def create_new_version(secret_id: str, value: str) -> int:
    """Creates a new secret version and returns the version number."""
    client = get_secret_manager_client()
    parent = f"projects/{PROJECT_ID}/secrets/{secret_id}"
    
    payload = value.encode("UTF-8")
    response = client.add_secret_version(
        request={"parent": parent, "payload": {"data": payload}}
    )
    
    # Version name format: projects/.../secrets/.../versions/{version_num}
    version_num = int(response.name.split("/")[-1])
    logger.info(f"Created new version {version_num} for secret {secret_id}")
    return version_num

def disable_previous_versions(secret_id: str, new_version: int):
    """Disables all versions of a secret except the newly created one."""
    client = get_secret_manager_client()
    parent = f"projects/{PROJECT_ID}/secrets/{secret_id}"
    
    versions = client.list_secret_versions(request={"parent": parent})
    
    for version in versions:
        version_num = int(version.name.split("/")[-1])
        # Only disable active versions that are not the new one
        if version_num != new_version and version.state == secretmanager.SecretVersion.State.ENABLED:
            try:
                client.disable_secret_version(request={"name": version.name})
                logger.info(f"Disabled version {version_num} of secret {secret_id}")
            except Exception as e:
                logger.warning(f"Could not disable version {version_num}: {e}")

def trigger_cloud_run_revision():
    """Triggers a new Cloud Run revision to pick up the latest secrets."""
    client = get_cloud_run_client()
    name = f"projects/{PROJECT_ID}/locations/{REGION}/services/{SERVICE_NAME}"
    
    service = client.get_service(name=name)
    
    # In Cloud Run v2, RevisionTemplate has labels and annotations directly.
    # We update a custom annotation to force a new revision.
    service.template.annotations["autohaus.cil/last-rotation"] = datetime.utcnow().isoformat()
    
    operation = client.update_service(request={"service": service})
    logger.info(f"Triggered Cloud Run revision update. Operation: {operation.operation.name}")
    result = operation.result()
    logger.info(f"Cloud Run revision update complete: {result.name}")

def write_rotation_event(secret_name: str, actor: str, mcp_invalidated: bool = False):
    """Writes a CREDENTIAL_ROTATED event to cil_events."""
    bq = BigQueryClient()
    
    payload = {
        "secret_name": secret_name,
        "rotation_timestamp": datetime.utcnow().isoformat() + "Z",
        "actor": actor,
        "previous_version_disabled": True
    }
    
    if mcp_invalidated:
        payload["mcp_sessions_invalidated"] = True
        
    event = CILEvent(
        event_id=str(uuid.uuid4()),
        event_type=EventType.CREDENTIAL_ROTATED,
        actor_type=ActorType.HUMAN,
        actor_id=actor,
        actor_role=ActorRole.SOVEREIGN,
        target_type=TargetType.ENTITY,
        target_id="AUTOHAUS_COS" if secret_name != "SECURITY_ACCESS_KEY_HASH" else "SECURITY_ACCESS_KEY_HASH",
        payload=payload
    )
    
    success = bq.insert_cil_event(event)
    if not success:
        raise Exception("Failed to write rotation event to BigQuery.")
    logger.info(f"Logged rotation event for {secret_name}")

def send_confirmation_sms(message: str):
    """Dispatches a Twilio SMS to Moaz."""
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_PHONE_NUMBER")
    # In a real scenario, this would be fetched from Policy Registry (rotation_sms_recipient)
    # For now, we assume it's in the environment as MOAZ_PHONE_NUMBER
    to_number = os.environ.get("MOAZ_PHONE_NUMBER")
    
    if not all([account_sid, auth_token, from_number, to_number]):
        logger.warning("Twilio credentials or recipient number missing. SMS skipped.")
        print(f"SMS WOULD SEND: {message}")
        return

    client = TwilioClient(account_sid, auth_token)
    try:
        client.messages.create(
            body=message,
            from_=from_number,
            to=to_number
        )
        logger.info("SMS confirmation sent.")
    except Exception as e:
        logger.error(f"Failed to send SMS: {e}")
        # Not strictly failing the whole script if SMS fails, but we should log it.
