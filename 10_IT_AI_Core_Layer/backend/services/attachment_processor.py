
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
    
    ontology_valid_names = []
    try:
        ontology_path = os.path.join(os.path.dirname(__file__), '..', 'registry', 'business_ontology.json')
        if os.path.exists(ontology_path):
            with open(ontology_path, 'r') as f:
                ontology = json.load(f)
            parent = ontology.get("business_structure", {}).get("parent_entity", {})
            if parent.get("legal_name"): ontology_valid_names.append(parent.get("legal_name").lower())
            if parent.get("display_name"): ontology_valid_names.append(parent.get("display_name").lower())
            # Read parent aliases array
            for alias in parent.get("aliases", []):
                ontology_valid_names.append(alias.lower())
            lanes = ontology.get("business_structure", {}).get("operating_lanes", [])
            for lane in lanes:
                if lane.get("legal_name"): ontology_valid_names.append(lane.get("legal_name").lower())
                if lane.get("alias"): ontology_valid_names.append(lane.get("alias").lower())
                # Read lane aliases array — this was missing and caused ENTITY_NAME_MISMATCH
                for alias in lane.get("aliases", []):
                    ontology_valid_names.append(alias.lower())
    except Exception as e:
        logger.error(f"Failed to load ontology: {e}")

    doc_type = raw_response.get("doc_type") or raw_response.get("document_type")
    
    for key, val in raw_response.items():
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict) and "extracted_value" in item:
                    try:
                        target_field = item.get("target_field", key)
                        val_str = str(item.get("extracted_value", ""))
                        lineage = dict(source_lineage)
                        
                        if val_str == "VIN_NOT_PROVIDED":
                            lineage["stub_type"] = "STUB_PENDING_VIN"
                        
                        if target_field == "bill_to_entity_name" and doc_type == "VENDOR_INVOICE":
                            if val_str.lower() not in ontology_valid_names:
                                # We'll raise the open question but continue processing the claim
                                try:
                                    from database.open_questions import raise_open_question
                                    from database.bigquery_client import BigQueryClient
                                    bq_client = BigQueryClient().client
                                    raise_open_question(
                                        bq_client=bq_client,
                                        question_type="ENTITY_MATCH_FAILURE",
                                        priority="HIGH",
                                        context={
                                            "input_reference": input_reference,
                                            "attempted_name": val_str
                                        },
                                        description=f"Extracted bill_to_entity_name '{val_str}' does not match any registered entity."
                                    )
                                except Exception as bqe:
                                    logger.warning(f"Failed to raise open question for mismatch: {bqe}")
                                val_str = "ENTITY_NAME_MISMATCH"
                        
                        claim_data = {
                            "source": source.value if hasattr(source, "value") else source,
                            "extractor_identity": extractor_identity,
                            "input_reference": input_reference,
                            "source_lineage": lineage,
                            "entity_type": item.get("entity_type", "UNKNOWN"),
                            "target_field": target_field,
                            "extracted_value": val_str,
                            "confidence": float(item.get("confidence", 1.0))
                        }
                        claims.append(ExtractedClaim.from_gemini_response(claim_data))
                    except Exception as e:
                        logger.error(f"Failed to unpack claim from {item}: {e}")
    
    logger.info(f"[ATTACHMENTS] Unpacked {len(claims)} claims from raw response.")
    return claims

class AttachmentProcessor:
    def __init__(self):
        self.bq = BigQueryClient()
        self.ws = WorkspaceService(user_to_impersonate="ahsin@autohausia.com")
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel(
            "gemini-2.5-flash",
            generation_config=genai.GenerationConfig(
                temperature=0.0,
                response_mime_type="application/json"
            )
        )

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
                    from pipeline.conflict_detector import process_claim, log_claim_processing_result
                    for claim in claims:
                        try:
                            result = await process_claim(claim, self.bq)
                            log_claim_processing_result(result)
                        except Exception as e:
                            logger.error(f"[ATTACHMENTS] Conflict detector error on claim {claim.claim_id}: {e}")
                    
                    data['filename'] = filename
                    data['source_message_id'] = message_id
                    extracted_data.append(data)

        if extracted_data:
            # Create a combined proposal for this message (or one per attachment)
            for item in extracted_data:
                await self._create_proposal(item, sender, subject, message_id)

    async def _extract_tier0_metrics(self, file_bytes: bytes, filename: str, sender: str, subject: str) -> Dict:
        """Uses Gemini 1.5 Flash to extract VINs, Costs, and Entity details from a PDF."""
        prompt = f"""Read only what is literally present in this document.
The document type is determined by the document's own header and content — not by context about the business receiving it.
Do not infer, assume, or hallucinate fields that are not explicitly present.
If a field is not found, return null for that field. Do not substitute plausible values.

If the document explicitly states "VIN: NOT PROVIDED" or similar, extract "VIN_NOT_PROVIDED" as the value with confidence 1.0.

You are the AutoHaus Tier 0 Extraction Agent.
Analyze this document (attached PDF) for an auto dealership.
Identify:
1. VINs (17 characters, or VIN_NOT_PROVIDED)
2. Exact Dollar Amounts (Purchase Price, Transport Cost, Auction Fees, Policy Premia)
3. Entity Names (Transport Carrier, Insurance Carrier, Auction House, Bank)
4. Dates (Purchase Date, Policy Start/End)
5. Document Type (AUCTION_RECEIPT, BOL, VENDOR_INVOICE, INSURANCE_CERT, BANK_STMT, TAX_DOC)
6. For VENDOR_INVOICE documents ONLY, additionally extract these into a "vendor_invoice_fields" array: 
   vendor_name, vendor_address, vendor_phone, vendor_email, bill_to_entity_name, bill_to_address, bill_to_account_number, contact_name, vehicle_year, vehicle_make, vehicle_model, vehicle_mileage, vehicle_stock_number, invoice_number, invoice_date, due_date, payment_terms, subtotal, tax_amount, total_amount, line_items (encode the entire array as a single JSON string), notes.
   Ensure bill_to_entity_name is always present if it exists.

Sender: {sender}
Subject: {subject}
Filename: {filename}

Return valid JSON ONLY, using arrays of extracted fact objects partitioned freely by key (e.g. "vins", "financials", "entities", "dates", "vendor_invoice_fields", etc).
Each extracted fact object MUST include exactly these fields:
  - confidence (float between 0.0 and 1.0)
  - entity_type (must be one of: VEHICLE, PERSON, VENDOR, DOCUMENT, UNKNOWN)
  - target_field (string, e.g., 'vin', 'bill_to_entity_name', 'subtotal', 'line_items')
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
            logger.info(f"[ATTACHMENTS] Raw Gemini text for {filename}: {text[:500]}...")
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
