
import os
import sys
import logging
import uuid
import json
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.cloud import bigquery

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.extraction_engine import classify_document, extract_fields, get_schema
from pipeline.entity_resolution import link_document_entities

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
logger = logging.getLogger("inbox_ingest")

SA_KEY_PATH = "/Users/moazsial/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/backend/auth/replit-sa-key.json"
ECOSYSTEM_FOLDER_ID = '1YhWi3cCIO-qX8r0hbzxM0zaX-_u0T-TI'

# Map doc types to folder names
FOLDER_MAP = {
    "VEHICLE_TITLE": "02_Titles",
    "AUCTION_RECEIPT": "06_Auctions",
    "INSURANCE_CERT": "04_Insurance",
    "DAMAGE_DISCLOSURE_IA": "08_Compliance",
    "SERVICE_RO": "05_Service",
    "TRANSPORT_INVOICE": "07_Transport",
    "FLOOR_PLAN_NOTE": "10_Finance",
    "BILL_OF_SALE": "03_Sales",
    "DEALER_PLATE": "08_Compliance",
    "TITLE_REASSIGNMENT": "02_Titles",
    "ODOMETER_DISCLOSURE": "08_Compliance"
}

def _get_folder_id(drive_service, folder_name):
    query = f"'{ECOSYSTEM_FOLDER_ID}' in parents and name = '{folder_name}' and trashed = false"
    results = drive_service.files().list(
        q=query, supportsAllDrives=True, includeItemsFromAllDrives=True, fields="files(id)"
    ).execute()
    files = results.get('files', [])
    return files[0]['id'] if files else None

def ingest():
    try:
        # Init Clients
        credentials = service_account.Credentials.from_service_account_file(SA_KEY_PATH)
        drive_service = build('drive', 'v3', credentials=credentials.with_scopes(['https://www.googleapis.com/auth/drive']))
        bq_client = bigquery.Client(credentials=credentials)

        # 1. Find 00_Inbox
        inbox_id = _get_folder_id(drive_service, "00_Inbox")
        if not inbox_id:
            logger.error("00_Inbox not found")
            return

        # 2. List items
        results = drive_service.files().list(
            q=f"'{inbox_id}' in parents and trashed = false",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            fields="files(id, name, mimeType)"
        ).execute()
        files = results.get('files', [])
        
        if not files:
            logger.info("Inbox is empty.")
            return

        logger.info(f"Ingesting {len(files)} files from Inbox...")

        for f in files:
            file_id = f['id']
            file_name = f['name']
            mime_type = f['mimeType']
            
            logger.info(f"\n>>> Processing: {file_name}")

            # For PDF/Images, we'd need OCR. For now, let's assume we can get text
            # In a real run, we'd use a PDF parser. 
            # Let's use simple text extraction for the first page if it's PDF.
            text_content = ""
            if mime_type == 'application/pdf':
                # Simplified: Download and extract text
                try:
                    import fitz # PyMuPDF
                    content = drive_service.files().get_media(fileId=file_id, supportsAllDrives=True).execute()
                    with open("temp.pdf", "wb") as pdf_file:
                        pdf_file.write(content)
                    
                    doc = fitz.open("temp.pdf")
                    # Get first 2 pages for classification
                    for page in doc[:2]:
                        text_content += page.get_text()
                    doc.close()
                except Exception as e:
                    logger.error(f"OCR/Text extraction failed for {file_name}: {e}")
                    continue
            else:
                logger.warning(f"Skipping non-PDF file: {file_name} [{mime_type}]")
                continue

            # 3. Classify
            doc_type, confidence = classify_document(text_content)
            logger.info(f"Result: {doc_type} ({confidence:.2f})")

            # 4. Route & Move
            target_folder_name = FOLDER_MAP.get(doc_type, "UNKNOWN")
            if target_folder_name != "UNKNOWN":
                target_folder_id = _get_folder_id(drive_service, target_folder_name)
                if target_folder_id:
                    # Move file
                    file = drive_service.files().get(fileId=file_id, fields='parents', supportsAllDrives=True).execute()
                    previous_parents = ",".join(file.get('parents'))
                    drive_service.files().update(
                        fileId=file_id,
                        addParents=target_folder_id,
                        removeParents=previous_parents,
                        supportsAllDrives=True
                    ).execute()
                    logger.info(f"Moved to {target_folder_name}")
                else:
                    logger.warning(f"Target folder {target_folder_name} not found in Ecosystem")
                    continue
            else:
                logger.info("Classified as UNKNOWN. Leaving in Inbox.")
                continue

            # 5. Extract & BQ
            document_id = str(uuid.uuid4())
            # Write to 'jobs' table first to track
            job_row = {
                "job_id": str(uuid.uuid4()),
                "document_id": document_id,
                "status": "PROCESSING",
                "created_at": datetime.utcnow().isoformat()
            }
            bq_client.insert_rows_json("autohaus-infrastructure.autohaus_cil.jobs", [job_row])
            
            # Extract fields
            extract_result = extract_fields(text_content, doc_type, document_id, bq_client=bq_client)
            
            if extract_result:
                # Entity Resolution
                link_document_entities(bq_client, document_id, extract_result['fields'], get_schema(doc_type))
                logger.info(f"Data ingested to BigQuery for {document_id}")
            
            # Update job status
            # (In a real system we'd update, here we just finish the loop)

        logger.info("\n✅ Ingestion run complete.")

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")

if __name__ == "__main__":
    ingest()
