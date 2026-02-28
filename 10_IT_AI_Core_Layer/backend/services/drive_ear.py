
import os
import json
import logging
import uuid
import asyncio
from datetime import datetime, timezone
from googleapiclient.discovery import build
from google.oauth2 import service_account

# C-OS Neural Components
from agents.router_agent import RouterAgent
from agents.iea_agent import InputEnrichmentAgent
from agents.attention_dispatcher import AttentionDispatcher
from routes.chat_stream import manager, build_plate_payload

logger = logging.getLogger("autohaus.drive_ear")

# Configuration
INBOX_FOLDER_NAME = "00_Inbox"

class DriveEar:
    def __init__(self):
        self._service = None
        self._inbox_id = None
        self.processed_files = set() # Optional: BigQuery is better for persistence
        
        # Neural Stack — gracefully degrade if GEMINI_API_KEY not configured
        try:
            self.router = RouterAgent()
        except EnvironmentError as e:
            logger.warning(f"[DRIVE EAR] RouterAgent unavailable: {e}")
            self.router = None
        try:
            self.iea = InputEnrichmentAgent()
        except EnvironmentError as e:
            logger.warning(f"[DRIVE EAR] IEA unavailable: {e}")
            self.iea = None
        try:
            self.dispatcher = AttentionDispatcher()
        except EnvironmentError as e:
            logger.warning(f"[DRIVE EAR] AttentionDispatcher unavailable: {e}")
            self.dispatcher = None

    @property
    def service(self):
        if not self._service:
            self._service = self._get_drive_service()
        return self._service

    @property
    def inbox_id(self):
        if not self._inbox_id:
            self._inbox_id = self._find_folder_id(INBOX_FOLDER_NAME)
        return self._inbox_id

    def _get_drive_service(self):
        sa_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
        if not sa_json:
            logger.warning("[DRIVE EAR] GCP_SERVICE_ACCOUNT_JSON not found. Ambient Listening disabled.")
            return None
        
        try:
            info = json.loads(sa_json)
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=['https://www.googleapis.com/auth/drive']
            )
            return build('drive', 'v3', credentials=credentials)
        except Exception as e:
            logger.error(f"[DRIVE EAR] Auth Failed: {e}")
            return None

    def _find_folder_id(self, folder_name):
        if not self.service: return None
        try:
            query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            items = results.get('files', [])
            if items:
                logger.info(f"[DRIVE EAR] Found {folder_name} ID: {items[0]['id']}")
                return items[0]['id']
            logger.warning(f"[DRIVE EAR] {folder_name} not found. Ensure shared with Service Account.")
            return None
        except Exception as e:
            logger.error(f"[DRIVE EAR] Folder Discovery Failed: {e}")
            return None

    async def register_watch(self, webhook_url: str):
        """Registers a push notification channel with Google Drive."""
        if not self.inbox_id:
            logger.error("[DRIVE EAR] Cannot register watch: Inbox ID not found.")
            return

        channel_id = str(uuid.uuid4())
        body = {
            "id": channel_id,
            "type": "web_hook",
            "address": webhook_url
        }
        
        try:
            logger.info(f"[DRIVE EAR] Registering watch on {self.inbox_id} for {webhook_url}")
            res = self.service.files().watch(fileId=self.inbox_id, body=body).execute()
            logger.info(f"[DRIVE EAR] Watch registered. Channel ID: {res.get('id')}")
            return res
        except Exception as e:
            logger.error(f"[DRIVE EAR] Watch registration failed: {e}")
            return None

    async def check_for_new_files(self):
        """Manually trigger a check of the inbox folder (called by webhook)."""
        if not self.inbox_id: return

        try:
            query = f"'{self.inbox_id}' in parents and trashed = false"
            results = self.service.files().list(q=query, fields="files(id, name, createdTime)").execute()
            files = results.get('files', [])

            for f in files:
                file_id = f['id']
                # In production, we'd check a database instead of a local set
                if file_id not in self.processed_files:
                    logger.info(f"[DRIVE EAR] Internal discovery: {f['name']}")
                    await self.process_ambient_file(f)
                    self.processed_files.add(file_id)
        except Exception as e:
            logger.error(f"[DRIVE EAR] Listing failed: {e}")

    async def process_ambient_file(self, file_metadata):
        """Routes file discovery through the full C-OS neural pipeline."""
        filename = file_metadata['name']
        discovery_text = f"Ambient Discovery in Drive: New file '{filename}' dropped in {INBOX_FOLDER_NAME}."
        
        iea_result = self.iea.evaluate(discovery_text)
        routed_intent = self.router.classify(discovery_text)
        attention_result = self.dispatcher.evaluate_event(discovery_text)
        
        plate_payload = build_plate_payload(routed_intent, urgency_score=attention_result.urgency_score)
        plate_payload.origin = "AMBIENT_DISCOVERY"
        plate_payload.suggested_action = f"Action Item: {attention_result.synthesized_message}"
        
        if attention_result.urgency_score < 8:
             plate_payload.strategy.skin = "AMBIENT_RECON"
             plate_payload.strategy.overlay = "ambient-discovery-shimmer"

        logger.info(f"[DRIVE EAR] Broadcasing Plate: {plate_payload.plate_id} | Urgency: {attention_result.urgency_score}")
        await manager.broadcast(plate_payload.model_dump())

try:
    drive_ear = DriveEar()
except Exception as e:
    logger.warning(f"[DRIVE EAR] Failed to initialize DriveEar: {e}")
    drive_ear = None
