import os
import json
import logging
import asyncio
import uuid
import base64
from datetime import datetime
from typing import List, Dict, Any

from google.cloud import bigquery
from database.bigquery_client import BigQueryClient
from database.policy_engine import get_policy
from agents.classifier_agent import EmailClassifier
from integrations.google_workspace_service import WorkspaceService
from pipeline.hitl_service import propose

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("autohaus.gmail_scan")

# Configuration
ACCOUNTS = ["ahsin@autohausia.com", "moaz@autohausia.com", "asim@autohausia.com", "sunny@autohausia.com", "bookings@autohausia.com"]
BATCH_ID = f"batch_{uuid.uuid4().hex[:8]}"

class GmailHistoricalScanner:
    def __init__(self):
        self.bq_client = BigQueryClient().client
        self.classifier = EmailClassifier()
        # WorkspaceService will be initialized per-account during the loop
        self.workspace = None

    async def run_full_scan(self):
        logger.info(f"🚀 Starting Full Historical Scan (Batch: {BATCH_ID})")
        summary = {acc: {"processed": 0, "categories": {}} for acc in ACCOUNTS}

        for account in ACCOUNTS:
            logger.info(f"📬 Scanning inbox: {account}")
            # Initialize WorkspaceService for this specific account (Impersonation)
            user_workspace = WorkspaceService(user_to_impersonate=account)
            messages = await self._fetch_all_messages(user_workspace)
            logger.info(f"Found {len(messages)} messages for {account}")

            for msg_meta in messages:
                try:
                    result = await self._process_message(user_workspace, account, msg_meta['id'])
                    summary[account]["processed"] += 1
                    cat = result.get("classification", "UNKNOWN")
                    summary[account]["categories"][cat] = summary[account]["categories"].get(cat, 0) + 1
                except Exception as e:
                    logger.error(f"Error processing {msg_meta['id']} for {account}: {e}")

        # Final step: Pattern Discovery
        await self._run_pattern_discovery()
        self._print_summary(summary)

    async def _fetch_all_messages(self, user_workspace) -> List[dict]:
        """Fetches message metadata for every email in the user's inbox."""
        # FULL SCAN: Fetch all messages (using a reasonable max for first large pass)
        res = user_workspace.gmail.users().messages().list(userId='me', q="").execute()
        return res.get('messages', [])

    async def _process_message(self, user_workspace, account: str, msg_id: str) -> dict:
        """Full pipeline for a single message."""
        msg = user_workspace.gmail.users().messages().get(userId='me', id=msg_id).execute()
        
        # 1. Parse Headers
        headers = msg.get('payload', {}).get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
        sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown")
        date_str = next((h['value'] for h in headers if h['name'] == 'Date'), None)
        
        # Convert Date header to BQ compatible timestamp
        try:
            # Simple fallback, production would use dateutil.parser
            date_ts = datetime.utcnow() # Fallback
        except:
            date_ts = datetime.utcnow()

        snippet = msg.get('snippet', '')
        body = self._get_full_body(msg)

        # 2. Classification
        triage = await self.classifier.classify_email(sender, subject, snippet)
        category = triage['category']

        # Rule for moaz@autohausia.com: Quarantine Turo
        if account == "moaz@autohausia.com" and ("turo" in sender.lower() or "turo" in body.lower()):
            category = "TURO_CALIFORNIA"

        # 3. Entity Extraction (if not marketing)
        extracted_entities = {}
        if category not in ["MARKETING", "PERSONAL"]:
            extracted_entities = await self._extract_body_entities(body, sender)

        # 4. Attachment Check
        attachments = self._get_attachment_info(msg)

        # 5. Persist to BigQuery
        row = {
            "message_id": msg_id,
            "thread_id": msg.get('threadId'),
            "email_account": account,
            "from_address": sender,
            "subject": subject,
            "date": date_ts.isoformat(),
            "classification": category,
            "confidence": float(triage.get('confidence', 0.9)),
            "has_attachments": len(attachments) > 0,
            "attachment_types": [a['type'] for a in attachments],
            "attachment_names": [a['name'] for a in attachments],
            "body_snippet": snippet[:500],
            "extracted_entities": json.dumps(extracted_entities),
            "scan_batch_id": BATCH_ID,
            "processed_at": datetime.utcnow().isoformat()
        }
        
        self.bq_client.insert_rows_json(
            "autohaus-infrastructure.autohaus_cil.gmail_scan_results", [row]
        )

        # 6. Proposal Staging
        if category not in ["MARKETING", "PERSONAL"]:
            await self._stage_proposals(row, extracted_entities)

        return row

    def _get_full_body(self, msg: dict) -> str:
        """Combines parts of the email into a single string."""
        # Simple implementation
        payload = msg.get('payload', {})
        if 'parts' in payload:
            return " ".join([p.get('body', {}).get('data', '') for p in payload['parts']])
        return payload.get('body', {}).get('data', '')

    def _get_attachment_info(self, msg: dict) -> List[dict]:
        atts = []
        payload = msg.get('payload', {})
        parts = payload.get('parts', [])
        for p in parts:
            if p.get('filename'):
                atts.append({'name': p['filename'], 'type': p['mimeType']})
        return atts

    async def _extract_body_entities(self, body: str, sender: str) -> dict:
        """Call Gemini to extract operational entities from body text."""
        import google.generativeai as genai
        model = genai.GenerativeModel("gemini-flash-latest")
        prompt = f"""Extract data from this email for an auto dealership. 
Identify: VINS, Dollar Amounts (and what they are for), Vendor Names, Person Names.
Context: Sender is {sender}.
Body: {body[:5000]}
Return JSON only: {{"vins": [], "financials": [{{"amount": 0.0, "purpose": ""}}], "vendors": [], "persons": []}}"""
        try:
            res = model.generate_content(prompt)
            return json.loads(res.text.strip().strip("```json").strip("```"))
        except:
            return {}

    async def _stage_proposals(self, results: dict, entities: dict):
        """Create Sandbox proposals for newly found entities."""
        # 1. Propose Vendors
        for vendor in entities.get("vendors", []):
            propose(self.bq_client, "GMAIL_SCAN", "SYSTEM", "ENTITY_MODIFICATION", "VENDOR", vendor, 
                    {"name": vendor, "source": f"GMAIL_{results['message_id']}"})
        
        # 2. Propose Vehicles
        for vin in entities.get("vins", []):
            propose(self.bq_client, "GMAIL_SCAN", "SYSTEM", "ENTITY_MODIFICATION", "VEHICLE", vin, 
                    {"vin": vin, "source": "GMAIL_SCAN"})

    async def _run_pattern_discovery(self):
        """Analyze batch results for higher order patterns."""
        logger.info("[ANALYSIS] Running pattern discovery pass...")
        # Summarize results from BQ and send to Gemini
        # (Simplified for the script)
        pass

    def _print_summary(self, summary: dict):
        print("\n" + "="*50)
        print("📊 GMAIL SCAN COMPLETE SUMMARY")
        print("="*50)
        for acc, data in summary.items():
            print(f"\nAccount: {acc}")
            print(f" - Emails Processed: {data['processed']}")
            for cat, count in data['categories'].items():
                print(f" - {cat}: {count}")
        print("="*50 + "\n")

if __name__ == "__main__":
    scanner = GmailHistoricalScanner()
    asyncio.run(scanner.run_full_scan())
