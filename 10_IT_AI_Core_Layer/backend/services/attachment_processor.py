
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
                # Read lane aliases array
                for alias in lane.get("aliases", []):
                    ontology_valid_names.append(alias.lower())
    except Exception as e:
        logger.error(f"Failed to load ontology: {e}")

    doc_type = raw_response.get("doc_type") or raw_response.get("document_type") or "UNKNOWN"
    fields = raw_response.get("fields", {})
    
    # Handle the new dictionary-based schema approach
    for target_field, field_data in fields.items():
        if field_data.get("value") is None:
            continue
            
        try:
            val_str = str(field_data.get("value", ""))
            lineage = dict(source_lineage)
            if "extraction_version_id" in raw_response:
                lineage["extraction_version_id"] = raw_response["extraction_version_id"]
            
            if val_str == "VIN_NOT_PROVIDED":
                lineage["stub_type"] = "STUB_PENDING_VIN"
            
            if target_field == "bill_to_entity_name" and doc_type == "VENDOR_INVOICE":
                if val_str.lower() not in ontology_valid_names:
                    # Raise open question
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
            
            # Map robust entity_type via rough legacy heuristic or default to DOCUMENT
            entity_type = "DOCUMENT"
            if target_field == "vin": entity_type = "VEHICLE"
            elif target_field in ("vendor_name", "transport_carrier", "auction_house"): entity_type = "VENDOR"
            elif target_field == "bill_to_entity_name": entity_type = "DOCUMENT"
            elif "name" in target_field: entity_type = "PERSON"

            claim_data = {
                "source": source.value if hasattr(source, "value") else source,
                "extractor_identity": extractor_identity,
                "input_reference": input_reference,
                "source_lineage": lineage,
                "entity_type": entity_type,
                "target_field": target_field,
                "extracted_value": val_str,
                "confidence": float(field_data.get("confidence", 1.0))
            }
            claims.append(ExtractedClaim.from_gemini_response(claim_data))
        except Exception as e:
            logger.error(f"Failed to unpack claim for {target_field}: {e}")
    
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
        """Extracts fields by integrating with extraction_engine and OCR Pipeline."""
        import tempfile
        import asyncio
        from pipeline.ocr_engine import _extract_via_gemini_vision
        from pipeline.extraction_engine import classify_document, extract_fields
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
            
        try:
            # 1. OCR the PDF
            text_content = await _extract_via_gemini_vision(tmp_path)
            if not text_content: 
                logger.error(f"[ATTACHMENTS] Empty OCR result for {filename}")
                return {}
             
            full_text = f"Email Details:\nSender: {sender}\nSubject: {subject}\nFilename: {filename}\n\nDocument Text:\n{text_content}"
            
            # 2. Classify
            doc_type, conf = await classify_document(full_text)
            if doc_type == "UNKNOWN":
                logger.warning(f"[ATTACHMENTS] Document type UNKNOWN for {filename}. Defaulting to VENDOR_INVOICE for heuristic fallback.")
                doc_type = "VENDOR_INVOICE"
            
            # 3. Extract Fields against schema
            file_id = "att_" + filename.replace(" ", "_")
            result = await extract_fields(full_text, doc_type, file_id, self.bq.client)
            
            if not result:
                logger.error(f"[ATTACHMENTS] Extraction returned nothing for {filename}")
                return {}
                
            return result
        except Exception as e:
            logger.error(f"[ATTACHMENTS] Extraction pipeline failed: {e}")
            return {}
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def _create_proposal(self, data: Dict, sender: str, subject: str, message_id: str):
        """Stages the extraction result in the HITL Governance system."""
        # Check for VINs to target vehicles
        vins = []
        if "fields" in data and "vin" in data["fields"]:
            vin_val = data["fields"]["vin"].get("value")
            if vin_val:
                vins.append(vin_val)
                
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
