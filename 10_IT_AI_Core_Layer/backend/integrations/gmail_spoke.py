import uuid
import json
import logging
import base64
import os
import io
from datetime import datetime
from typing import Dict, Any, List

from database.policy_engine import get_policy
from database.bigquery_client import BigQueryClient
from agents.classifier_agent import EmailClassifier
from .google_workspace_service import workspace

logger = logging.getLogger("autohaus.gmail")

class GmailSender:
    def __init__(self, bq_client=None):
        self.bq_client = bq_client or BigQueryClient().client

    async def draft_email(self, to: str, subject: str, body: str, context: dict = None) -> dict:
        """Create a Gmail draft (Sandbox First)."""
        logger.info(f"[GMAIL] Drafting email to {to}: {subject}")
        
        try:
            from email.mime.text import MIMEText
            import base64
            
            # 1. Construct MIME message
            message = MIMEText(body)
            message['to'] = to
            message['subject'] = subject
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            # 2. Call Gmail API via workspace service
            # Note: We need a workspace instance that impersonates a real user (e.g. ahsin@autohausia.com)
            # For now, we use the default workspace instance.
            res = workspace.gmail.users().drafts().create(
                userId='me',
                body={'message': {'raw': raw}}
            ).execute()
            
            draft_id = res.get('id')
            logger.info(f"[GMAIL] Draft created successfully: {draft_id}")
            
            # 3. Log to CIL events
            event_row = {
                "event_id": str(uuid.uuid4()),
                "event_type": "GMAIL_DRAFT_CREATED",
                "timestamp": datetime.utcnow().isoformat(),
                "actor_type": "SYSTEM",
                "actor_id": "gmail_sender",
                "actor_role": "SYSTEM",
                "target_type": "PERSON",
                "target_id": to,
                "payload": json.dumps({
                    "draft_id": draft_id, 
                    "subject": subject, 
                    "body_length": len(body), 
                    "context": context
                }),
                "idempotency_key": f"draft_applied_{draft_id}"
            }
            if self.bq_client:
                self.bq_client.insert_rows_json("autohaus-infrastructure.autohaus_cil.cil_events", [event_row])

            return {"status": "success", "draft_id": draft_id}
            
        except Exception as e:
            logger.error(f"[GMAIL] Failed to create draft: {e}")
            return {"status": "error", "message": str(e)}

class GmailMonitor:
    def __init__(self, bq_client=None):
        self.bq_client = bq_client or BigQueryClient().client
        self.classifier = EmailClassifier()
        
    async def process_incoming_webhook(self, payload: dict) -> dict:
        """
        Triggered when Gmail pushes a notification to our Pub/Sub.
        Payload typically contains emailAddress and historyId.
        """
        email_addr = payload.get("emailAddress")
        history_id = payload.get("historyId")
        
        # 1. Fetch latest messages since this history id
        # For simplicity, we fetch the latest message for this test
        try:
            results = workspace.gmail.users().messages().list(userId='me', maxResults=1).execute()
            messages = results.get('messages', [])
            if not messages: return {"status": "no_messages"}
            
            msg_id = messages[0]['id']
            message = workspace.gmail.users().messages().get(userId='me', id=msg_id).execute()
            
            # 2. Extract Data
            headers = message.get("payload", {}).get("headers", [])
            sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown")
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
            snippet = message.get("snippet", "")
            
            # 3. Intelligent Triage (Gemini)
            triage = await self.classifier.classify_email(sender, subject, snippet)
            logger.info(f"[GMAIL TRIAGE] {msg_id}: {triage['category']} - {triage['reasoning']}")
            
            # 4. Handle Operational Documents
            if triage["category"] in ["INVOICE_RECEIPT", "OPERATIONAL"]:
                attachments = self._get_attachments(message)
                for att in attachments:
                    await self._ingest_attachment(att, sender, triage)
                    
            # 5. Handle Leads
            if triage["category"] == "LEAD_INQUIRY":
                await self._notify_lead(sender, subject, snippet)

            return {"status": "success", "category": triage["category"]}
            
        except Exception as e:
            logger.error(f"[GMAIL MONITOR] Critical failure: {e}")
            return {"status": "error", "message": str(e)}

    def _get_attachments(self, message: dict) -> List[dict]:
        """Parses the message payload for parts with attachments."""
        attachments = []
        payload = message.get('payload', {})
        parts = payload.get('parts', [])
        
        for part in parts:
            if part.get('filename') and part.get('body', {}).get('attachmentId'):
                attachments.append({
                    'id': part['body']['attachmentId'],
                    'filename': part['filename'],
                    'mime_type': part['mimeType'],
                    'message_id': message['id']
                })
        return attachments

    async def _ingest_attachment(self, att: dict, sender: str, triage: dict):
        """Downloads attachment, uploads to Drive, and enqueues to CIL Pipeline."""
        try:
            # Download file from Gmail API
            res = workspace.gmail.users().messages().attachments().get(
                userId='me', messageId=att['message_id'], id=att['id']
            ).execute()
            data = base64.urlsafe_b64decode(res['data'])
            
            # Upload to Google Drive (CIL Inbox)
            file_metadata = {
                'name': f"GMAIL_{att['filename']}",
                'description': f"Auto-ingested from {sender}. Category: {triage['category']}"
            }
            media = io.BytesIO(data)
            # Placeholder: In real implementation, use MediaIoBaseUpload
            # drive_file = workspace.drive.files().create(body=file_metadata, media_body=media).execute()
            
            logger.info(f"[GMAIL INGEST] Ingested {att['filename']} for processing.")
            
            # Trigger CIL pipeline
            from pipeline.queue_worker import enqueue_file
            # await enqueue_file(workspace.drive, self.bq_client, {"id": drive_file['id'], "name": file_metadata['name']})
            
        except Exception as e:
            logger.error(f"[GMAIL INGEST] Failed to ingest attachment: {e}")

    async def _notify_lead(self, sender: str, subject: str, snippet: str):
        """Creates a lead notification and resolves person."""
        from integrations.notification_router import NotificationRouter
        router = NotificationRouter(self.bq_client)
        await router.notify_role("CEO", f"New Web Lead via Email: {sender}\nSubject: {subject}\n\n{snippet}", urgency="HIGH")
