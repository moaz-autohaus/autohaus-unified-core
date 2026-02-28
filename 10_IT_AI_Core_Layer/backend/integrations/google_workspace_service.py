import os
import json
import logging
from googleapiclient.discovery import build
from google.oauth2 import service_account

logger = logging.getLogger("autohaus.workspace")

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar'
]

class WorkspaceService:
    """
    Central provider for Google Workspace APIs.
    Uses the service account from environment or local auth key.
    """
    def __init__(self, user_to_impersonate: str = None):
        self.user_email = user_to_impersonate or "ahsin@autohausia.com"
        self._drive = None
        self._gmail = None
        self._calendar = None
        self.credentials = self._load_credentials()

    def _load_credentials(self):
        sa_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
        if sa_json:
            info = json.loads(sa_json)
            creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        else:
            local_paths = [
                os.path.join(os.path.dirname(__file__), "..", "auth", "replit-sa-key.json"),
                "/Users/moazsial/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/backend/auth/replit-sa-key.json",
            ]
            key_path = next((p for p in local_paths if os.path.exists(p)), None)
            if key_path is None:
                logger.warning("No GCP credentials found (GCP_SERVICE_ACCOUNT_JSON not set, key file not found). Google Workspace features will be unavailable.")
                return None
            creds = service_account.Credentials.from_service_account_file(key_path, scopes=SCOPES)

        if creds is None:
            return None
        # If impersonation is required (for Gmail/Calendar access on a specific user)
        if self.user_email and "@autohausia.com" in self.user_email:
            return creds.with_subject(self.user_email)
        return creds

    @property
    def drive(self):
        if not self._drive:
            self._drive = build('drive', 'v3', credentials=self.credentials)
        return self._drive

    @property
    def gmail(self):
        if not self._gmail:
            self._gmail = build('gmail', 'v1', credentials=self.credentials)
        return self._gmail

    @property
    def calendar(self):
        if not self._calendar:
            self._calendar = build('calendar', 'v3', credentials=self.credentials)
        return self._calendar

# Shared instances
workspace = WorkspaceService()
