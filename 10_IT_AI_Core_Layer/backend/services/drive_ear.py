
import os
import time
import json
import logging
import asyncio
from datetime import datetime, timezone
from googleapiclient.discovery import build
from google.oauth2 import service_account

# C-OS Neural Components
from agents.router_agent import RouterAgent
from agents.iea_agent import InputEnrichmentAgent
from agents.attention_dispatcher import AttentionDispatcher
from routes.chat_stream import manager, build_plate_payload, _resolve_skin

logger = logging.getLogger("autohaus.drive_ear")

# Configuration
INBOX_FOLDER_NAME = "00_Inbox"
POLL_INTERVAL = 30  # seconds

class DriveEar:
    def __init__(self):
        self.service = self._get_drive_service()
        self.inbox_id = self._find_folder_id(INBOX_FOLDER_NAME)
        self.processed_files = set()
        
        # Neural Stack
        self.router = RouterAgent()
        self.iea = InputEnrichmentAgent()
        self.dispatcher = AttentionDispatcher()

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

    async def poll_forever(self):
        """The main ambient listening loop."""
        logger.info(f"[DRIVE EAR] Neural Membrane monitoring started on {INBOX_FOLDER_NAME}")
        
        while True:
            if not self.service or not self.inbox_id:
                # Try to re-discover periodically if missing
                self.service = self._get_drive_service()
                self.inbox_id = self._find_folder_id(INBOX_FOLDER_NAME)
                await asyncio.sleep(POLL_INTERVAL)
                continue

            try:
                query = f"'{self.inbox_id}' in parents and trashed = false"
                results = self.service.files().list(q=query, fields="files(id, name, createdTime)").execute()
                files = results.get('files', [])

                for f in files:
                    file_id = f['id']
                    if file_id not in self.processed_files:
                        logger.info(f"[DRIVE EAR] Ambient Discovery: New file detected: {f['name']}")
                        await self.process_ambient_file(f)
                        self.processed_files.add(file_id)

            except Exception as e:
                logger.error(f"[DRIVE EAR] Polling Error: {e}")

            await asyncio.sleep(POLL_INTERVAL)

    async def process_ambient_file(self, file_metadata):
        """Routes file discovery through the full C-OS neural pipeline."""
        filename = file_metadata['name']
        discovery_text = f"Ambient Discovery in Drive: New file '{filename}' dropped in {INBOX_FOLDER_NAME}."
        
        # 1. IEA Classification
        iea_result = self.iea.evaluate(discovery_text)
        
        # 2. Router Intent Extraction
        routed_intent = self.router.classify(discovery_text)
        
        # 3. Attention Dispatcher
        attention_result = self.dispatcher.evaluate_event(discovery_text)
        
        # 4. WebSocket Push (High Urgency)
        # Even if urgency is low, we push for ambient awareness
        plate_payload = build_plate_payload(routed_intent, urgency_score=attention_result.urgency_score)
        plate_payload["origin"] = "AMBIENT_DISCOVERY"
        plate_payload["suggested_action"] = f"Action Item: {attention_result.synthesized_message}"
        
        # Force a specific color/skin for discovery if not high urgency
        if attention_result.urgency_score < 8:
             plate_payload["strategy"]["skin"] = "AMBIENT_RECON"
             plate_payload["strategy"]["overlay"] = "ambient-discovery-shimmer"

        logger.info(f"[DRIVE EAR] Broadcasing Plate: {plate_payload['plate_id']} | Urgency: {attention_result.urgency_score}")
        await manager.broadcast(plate_payload)

drive_ear = DriveEar()
