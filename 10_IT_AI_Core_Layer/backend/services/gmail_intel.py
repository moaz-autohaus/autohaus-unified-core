
import os
import json
import logging
import asyncio
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any

from database.bigquery_client import BigQueryClient
from agents.classifier_agent import EmailClassifier
from integrations.google_workspace_service import WorkspaceService
from pipeline.hitl_service import propose
from models.claims import ExtractedClaim, ClaimSource

logger = logging.getLogger("autohaus.gmail_intel")

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

ACCOUNTS_ORDER = [
    "ahsin@autohausia.com", 
    "moaz@autohausia.com", 
    "bookings@autohausia.com",
    "sunny@autohausia.com", 
    "asim@autohausia.com"
]

class GmailIntelService:
    def __init__(self):
        self.bq = BigQueryClient()
        self.classifier = EmailClassifier()

    async def run_full_scan_sequence(self, limit_per_batch: int = 100):
        """
        Runs the full scan sequence across all accounts in the specified order.
        """
        for account in ACCOUNTS_ORDER:
            logger.info(f"📬 Starting FULL SCAN for {account}")
            await self.scan_account_full(account, limit_per_batch)

    async def scan_account_full(self, account: str, limit_per_batch: int = 100):
        """
        Paginates through the entire inbox of an account.
        """
        batch_id = f"full_scan_{uuid.uuid4().hex[:8]}"
        ws = WorkspaceService(user_to_impersonate=account)
        next_page_token = None
        
        total_processed = 0
        stats = {
            "processed": 0,
            "categories": {},
            "vins": [],
            "vendors": [],
            "attachments": 0,
            "errors": 0
        }

        while True:
            try:
                results = ws.gmail.users().messages().list(
                    userId='me', 
                    maxResults=limit_per_batch,
                    pageToken=next_page_token
                ).execute()
                
                messages = results.get('messages', [])
                if not messages:
                    break

                for msg_meta in messages:
                    msg_id = msg_meta['id']
                    
                    if await self._is_already_processed(msg_id, account):
                        logger.info(f"[GMAIL INTEL] Skipping {msg_id} (Already in BQ)")
                        continue
                    
                    try:
                        result = await self._process_message(ws, account, msg_id, batch_id)
                        stats["processed"] += 1
                        cat = result["classification"]
                        stats["categories"][cat] = stats["categories"].get(cat, 0) + 1
                        
                        entities = json.loads(result["extracted_entities"])
                        def get_val(x): return x.get("extracted_value") if isinstance(x, dict) else x
                        stats["vins"].extend([get_val(v) for v in entities.get("vins", [])])
                        stats["vendors"].extend([get_val(v) for v in entities.get("vendors", [])])
                        if result["has_attachments"]:
                            stats["attachments"] += 1

                    except Exception as e:
                        logger.error(f"[GMAIL INTEL] Error processing {msg_id}: {e}")
                        stats["errors"] += 1
                    
                    await asyncio.sleep(0.05)

                next_page_token = results.get('nextPageToken')
                if not next_page_token:
                    break

            except Exception as e:
                logger.error(f"[GMAIL INTEL] Batch fetch failed for {account}: {e}")
                break

        self._log_summary(account, stats)
        return stats

    async def _is_already_processed(self, message_id: str, account: str) -> bool:
        query = f"""
            SELECT message_id 
            FROM `autohaus-infrastructure.autohaus_cil.gmail_scan_results`
            WHERE message_id = '{message_id}' AND email_account = '{account}'
            LIMIT 1
        """
        try:
            results = self.bq.client.query(query).result()
            return len(list(results)) > 0
        except:
            return False

    async def _process_message(self, ws: WorkspaceService, account: str, msg_id: str, batch_id: str):
        msg = ws.gmail.users().messages().get(userId='me', id=msg_id).execute()
        
        headers = msg.get('payload', {}).get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
        sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown")
        snippet = msg.get('snippet', '')
        
        # 1. Classification
        triage = await self.classifier.classify_email(sender, subject, snippet)
        category = triage['category']

        # 2. Custom Rules
        if account == "moaz@autohausia.com" and "turo" in sender.lower():
            category = "TURO_CALIFORNIA"
        elif account == "bookings@autohausia.com":
            category = "CUSTOMER_LEAD"

        # 3. Entity Extraction
        body = self._get_full_body(msg)
        extracted_entities = {}
        if category not in ["MARKETING", "PERSONAL", "TURO_CALIFORNIA"]:
            extracted_entities = await self._extract_entities(body, sender)
            
            # Hydrate into ExtractedClaim framework
            lineage = {
                "model": "gemini-1.5-flash",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            claims = unpack_to_claims(
                raw_response=extracted_entities,
                source=ClaimSource.GMAIL,
                extractor_identity="gmail_intel._extract_entities",
                input_reference=msg_id,
                source_lineage=lineage
            )
            # Claims are assembled; Task 1.2 completed for this node. Pipeline will handle database persistence in Task 2.
            from pipeline.conflict_detector import process_claim, log_claim_processing_result
            for claim in claims:
                try:
                    result = await process_claim(claim, self.bq)
                    log_claim_processing_result(result)
                except Exception as e:
                    logger.error(f"[GMAIL INTEL] Conflict detector error on claim {claim.claim_id}: {e}")

        # 4. Attachments
        attachments = self._get_attachments(msg)

        # 5. Persist
        row = {
            "message_id": msg_id,
            "thread_id": msg.get('threadId'),
            "email_account": account,
            "from_address": sender,
            "subject": subject,
            "date": datetime.now(timezone.utc).isoformat(),
            "classification": category,
            "confidence": float(triage.get('confidence', 0.9)),
            "body_snippet": snippet[:500],
            "has_attachments": len(attachments) > 0,
            "attachment_names": [a['name'] for a in attachments],
            "extracted_entities": json.dumps(extracted_entities),
            "scan_batch_id": batch_id,
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        
        self.bq.client.insert_rows_json(
            "autohaus-infrastructure.autohaus_cil.gmail_scan_results", [row]
        )

        # 6. STAGE PROPOSALS (Action Center)
        await self._stage_proposals(row, extracted_entities)

        return row

    async def _stage_proposals(self, row: dict, entities: dict):
        """
        Creates HITL events for entities discovered in the Gmail scan.
        """
        message_id = row["message_id"]
        account = row["email_account"]
        category = row["classification"]

        def get_val(x): return x.get("extracted_value") if isinstance(x, dict) else x

        # A. Vendor Proposals
        for vendor_raw in entities.get("vendors", []):
            vendor = get_val(vendor_raw)
            propose(
                bq_client=self.bq.client,
                actor_user_id="GMAIL_INTEL",
                actor_role="SYSTEM",
                action_type="ENTITY_MODIFICATION",
                target_type="VENDOR",
                target_id=vendor,
                payload={
                    "source": "GMAIL_SCAN",
                    "vendor_name": vendor,
                    "found_in_account": account,
                    "message_id": message_id
                },
                reason=f"Vendor '{vendor}' identified in email from {row['from_address']}."
            )

        # B. Vehicle Proposals
        for vin_raw in entities.get("vins", []):
            vin = get_val(vin_raw)
            propose(
                bq_client=self.bq.client,
                actor_user_id="GMAIL_INTEL",
                actor_role="SYSTEM",
                action_type="ENTITY_MODIFICATION",
                target_type="VEHICLE",
                target_id=vin,
                payload={
                    "source": "GMAIL_SCAN",
                    "vin": vin,
                    "account": account,
                    "message_id": message_id
                },
                reason=f"Vehicle VIN {vin} detected in email correspondence."
            )

        # C. Lead Proposals
        if category in ["CUSTOMER_LEAD", "LEAD_INQUIRY"]:
            persons_list = entities.get("persons", [])
            name = get_val(persons_list[0]) if persons_list else "Unknown"
            propose(
                bq_client=self.bq.client,
                actor_user_id="GMAIL_INTEL",
                actor_role="SYSTEM",
                action_type="ENTITY_MODIFICATION",
                target_type="LEAD",
                target_id=row["from_address"],
                payload={
                    "name": name,
                    "email": row["from_address"],
                    "source": "GMAIL_BOOKINGS"
                },
                reason=f"New booking lead identified: {name} ({row['from_address']})"
            )

        # D. Insurance Proposals
        if category == "INSURANCE_CORRESPONDENCE":
            vendors_list = entities.get("vendors", [])
            carrier = get_val(vendors_list[0]) if vendors_list else "Unknown"
            
            propose(
                bq_client=self.bq.client,
                actor_user_id="GMAIL_INTEL",
                actor_role="SYSTEM",
                action_type="ENTITY_MODIFICATION",
                target_type="INSURANCE",
                target_id=message_id,
                payload={
                    "source": "GMAIL_SCAN",
                    "carrier": carrier,
                    "policy_ref": get_val(entities.get("policy_ref")) or "Check Attachment"
                },
                reason="Insurance-related correspondence detected requiring policy update."
            )

    async def _extract_entities(self, body: str, sender: str) -> dict:
        import google.generativeai as genai
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = f"""Extract data from this email for an auto dealership. 
Identify: VINS, Dollar Amounts, Vendor Names.
Sender: {sender}. Body: {body[:3000]}

Return valid JSON ONLY, using arrays of extracted fact objects.
Each extracted fact object MUST include exactly these fields:
  - confidence (float between 0.0 and 1.0)
  - entity_type (must be one of: VEHICLE, PERSON, VENDOR, DOCUMENT, UNKNOWN)
  - target_field (string, e.g., 'vin', 'purchase_price', 'name')
  - extracted_value (string, the asserted value)

Example output:
{{
  "vins": [
    {{"extracted_value": "WBA123...", "confidence": 0.95, "entity_type": "VEHICLE", "target_field": "vin"}}
  ],
  "financials": [],
  "vendors": [
    {{"extracted_value": "Acme Transport", "confidence": 0.90, "entity_type": "VENDOR", "target_field": "vendor_name"}}
  ]
}}"""
        try:
            res = await model.generate_content_async(prompt)
            return json.loads(res.text.strip().strip("```json").strip("```"))
        except:
            return {}

    def _get_attachments(self, msg: dict) -> List[dict]:
        atts = []
        payload = msg.get('payload', {})
        for p in payload.get('parts', []):
            if p.get('filename'):
                atts.append({'name': p['filename'], 'type': p['mimeType']})
        return atts

    def _get_full_body(self, msg: dict) -> str:
        payload = msg.get('payload', {})
        if 'parts' in payload:
            return " ".join([p.get('body', {}).get('data', '') for p in payload['parts']])
        return payload.get('body', {}).get('data', '')

    def _log_summary(self, account: str, stats: dict):
        logger.info(f"\n--- {account} SCAN SUMMARY ---")
        logger.info(f"Total Processed: {stats['processed']}")
        logger.info(f"Categories: {json.dumps(stats['categories'], indent=2)}")
        logger.info(f"VINs: {list(set(stats['vins']))}")
        logger.info(f"Vendors: {list(set(stats['vendors']))}")
        logger.info(f"Attachments: {stats['attachments']}")
        logger.info(f"Errors: {stats['errors']}\n")

gmail_intel = GmailIntelService()
