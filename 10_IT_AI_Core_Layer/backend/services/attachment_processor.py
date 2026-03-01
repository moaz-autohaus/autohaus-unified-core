
import os
import io
import json
import base64
import logging
import asyncio
from typing import List, Dict, Any
from datetime import datetime, timezone

from database.bigquery_client import BigQueryClient
from integrations.google_workspace_service import WorkspaceService
from pipeline.hitl_service import propose
from models.claims import ExtractedClaim, ClaimSource
import google.generativeai as genai
from google.cloud import bigquery

logger = logging.getLogger("autohaus.attachment_processor")

def unpack_to_claims(raw_response: dict, 
                     source: ClaimSource,
                     extractor_identity: str,
                     input_reference: str,
                     source_lineage: dict) -> List[ExtractedClaim]:
    claims = []
    for key, val in raw_response.items():
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict) and "extracted_value" in item:
                    try:
                        claim_data = {
                            "source": source.value if hasattr(source, "value") else source,
                            "extractor_identity": extractor_identity,
                            "input_reference": input_reference,
                            "source_lineage": source_lineage,
                            "entity_type": item.get("entity_type", "UNKNOWN"),
                            "target_field": item.get("target_field", key),
                            "extracted_value": str(item.get("extracted_value", "")),
                            "confidence": float(item.get("confidence", 1.0))
                        }
                        claims.append(ExtractedClaim.from_gemini_response(claim_data))
                    except Exception as e:
                        logger.error(f"Failed to unpack claim from {item}: {e}")
    return claims

class AttachmentProcessor:
    def __init__(self):
        self.bq = BigQueryClient()
        self.ws = WorkspaceService(user_to_impersonate="ahsin@autohausia.com")
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    async def process_ahsin_attachments(self, limit: int = 50):
        """
        Batches through Ahsin's inbox to find and extract Tier 0 data from PDFs.
        """
        # 1. Query for messages with attachments that haven't been processed for tier-0 yet
        query = """
            SELECT message_id, subject, from_address, date
            FROM `autohaus-infrastructure.autohaus_cil.gmail_scan_results`
            WHERE email_account = 'ahsin@autohausia.com' 
            AND has_attachments = TRUE
            AND message_id NOT IN (
                SELECT target_id FROM `autohaus-infrastructure.autohaus_cil.hitl_events` 
                WHERE action_type = 'TIER_0_EXTRACTION'
            )
            LIMIT @limit
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("limit", "INT64", limit)]
        )
        messages = list(self.bq.client.query(query, job_config=job_config).result())
        
        logger.info(f"[ATTACHMENTS] Found {len(messages)} messages for Tier 0 extraction.")
        
        for msg_row in messages:
            try:
                await self.process_message_attachments(msg_row.message_id, msg_row.subject, msg_row.from_address)
                await asyncio.sleep(0.5) # Quota friendly
            except Exception as e:
                logger.error(f"[ATTACHMENTS] Failed for {msg_row.message_id}: {e}")

    async def process_message_attachments(self, message_id: str, subject: str, sender: str):
        """Fetches and extracts data from all PDFs in a single message."""
        msg = self.ws.gmail.users().messages().get(userId='me', id=message_id).execute()
        parts = msg.get('payload', {}).get('parts', [])
        
        extracted_data = []
        
        for part in parts:
            if part.get('mimeType') == 'application/pdf':
                att_id = part.get('body', {}).get('attachmentId')
                filename = part.get('filename')
                if not att_id: continue
                
                logger.info(f"[ATTACHMENTS] Extracting from {filename} ({message_id})")
                
                # Fetch bytes
                att = self.ws.gmail.users().messages().attachments().get(
                    userId='me', messageId=message_id, id=att_id
                ).execute()
                
                file_bytes = base64.urlsafe_b64decode(att['data'])
                
                # Extract via Gemini
                data = await self._extract_tier0_metrics(file_bytes, filename, sender, subject)
                logger.info(f"[ATTACHMENTS] Extracted: {json.dumps(data)}")
                if data:
                    lineage = {
                        "model": "gemini-2.5-flash",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    claims = unpack_to_claims(
                        raw_response=data,
                        source=ClaimSource.ATTACHMENT,
                        extractor_identity="attachment_processor._extract_tier0_metrics",
                        input_reference=message_id,
                        source_lineage=lineage
                    )
                    # Task 1.2 fulfilled for attachment extraction
                    
                    data['filename'] = filename
                    data['source_message_id'] = message_id
                    extracted_data.append(data)

        if extracted_data:
            # Create a combined proposal for this message (or one per attachment)
            for item in extracted_data:
                await self._create_proposal(item, sender, subject, message_id)

    async def _extract_tier0_metrics(self, file_bytes: bytes, filename: str, sender: str, subject: str) -> Dict:
        """Uses Gemini 1.5 Flash to extract VINs, Costs, and Entity details from a PDF."""
        prompt = f"""You are the AutoHaus Tier 0 Extraction Agent.
Analyze this document (attached PDF) for an auto dealership.
Identify:
1. VINs (17 characters)
2. Exact Dollar Amounts (Purchase Price, Transport Cost, Auction Fees, Policy Premia)
3. Entity Names (Transport Carrier, Insurance Carrier, Auction House, Bank)
4. Dates (Purchase Date, Policy Start/End)
5. Document Type (AUCTION_RECEIPT, BOL, INSURANCE_CERT, BANK_STMT, TAX_DOC)

Sender: {sender}
Subject: {subject}
Filename: {filename}

Return valid JSON ONLY, using arrays of extracted fact objects.
Each extracted fact object MUST include exactly these fields:
  - confidence (float between 0.0 and 1.0)
  - entity_type (must be one of: VEHICLE, PERSON, VENDOR, DOCUMENT, UNKNOWN)
  - target_field (string, e.g., 'vin', 'transport_cost', 'start_date')
  - extracted_value (string, the asserted value)

Example output:
{{
  "doc_type": "AUCTION_RECEIPT",
  "vins": [
    {{"extracted_value": "12345678901234567", "confidence": 0.99, "entity_type": "VEHICLE", "target_field": "vin"}}
  ],
  "financials": [
    {{"extracted_value": "500.0", "confidence": 1.0, "entity_type": "DOCUMENT", "target_field": "transport_cost"}}
  ],
  "entities": [
    {{"extracted_value": "Carrier ABC", "confidence": 0.9, "entity_type": "VENDOR", "target_field": "transport_carrier"}}
  ],
  "dates": [
    {{"extracted_value": "2026-02-21", "confidence": 1.0, "entity_type": "DOCUMENT", "target_field": "purchase_date"}}
  ]
}}"""
        try:
            # Inline bytes to Gemini
            response = self.model.generate_content([
                prompt,
                { "mime_type": "application/pdf", "data": file_bytes }
            ])
            text = response.text.strip().strip("```json").strip("```")
            return json.loads(text)
        except Exception as e:
            logger.error(f"[ATTACHMENTS] Gemini extraction failed: {e}")
            return {}

    async def _create_proposal(self, data: Dict, sender: str, subject: str, message_id: str):
        """Stages the extraction result in the HITL Governance system."""
        # Check for VINs to target vehicles
        def get_val(x): return x.get("extracted_value") if isinstance(x, dict) else x
        
        vins = [get_val(v) for v in data.get("vins", [])]
        target_id = vins[0] if vins else message_id
        target_type = "VEHICLE" if vins else "EMAIL_ATTACHMENT"
        
        payload = {
            "source": "ATTACHMENT_EXTRACTION",
            "message_id": message_id,
            "filename": data.get("filename"),
            "doc_data": data
        }
        
        # We use actor 'attachment_agent' role 'SYSTEM'
        # bq_client is passed to propose
        logger.info(f"[ATTACHMENTS] Creating proposal for {target_id} ({target_type})")
        propose(
            bq_client=self.bq.client,
            actor_user_id="attachment_agent",
            actor_role="SYSTEM",
            action_type="TIER_0_EXTRACTION",
            target_type=target_type,
            target_id=target_id,
            payload=payload,
            reason=f"Extracted Tier 0 data from {data.get('filename')} in Ahsin's inbox."
        )

attachment_processor = AttachmentProcessor()
