
import os
import sys
import logging
import json
from datetime import datetime
from google.cloud import bigquery
from google.oauth2 import service_account

# Set up logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
logger = logging.getLogger("test_extraction")

# Ensure backend is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.extraction_engine import classify_document, extract_fields

# Define service account path
SA_KEY_PATH = "/Users/moazsial/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/backend/auth/replit-sa-key.json"

def run_test_on_file(file_path):
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return

    logger.info(f"Reading file: {file_path}")
    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Classification
    logger.info("--- 1. Classification ---")
    doc_type, confidence = classify_document(content)
    logger.info(f"Classified as: {doc_type} (Confidence: {confidence:.2f})")

    if doc_type == "UNKNOWN":
        logger.error("Could not classify document. Stopping test.")
        return

    # 2. Extraction
    logger.info("--- 2. Extraction ---")
    # Set up a fake BigQuery client if possible or just run without it
    bq_client = None
    if os.path.exists(SA_KEY_PATH):
        try:
            credentials = service_account.Credentials.from_service_account_file(SA_KEY_PATH)
            bq_client = bigquery.Client(credentials=credentials)
            logger.info("BigQuery client initialized for test audit.")
        except Exception as e:
            logger.warning(f"Could not init BQ client: {e}")

    result = extract_fields(content, doc_type, "TEST_ID_001", bq_client=bq_client)
    
    if result:
        print("\n" + "="*50)
        print(f"EXTRACTION RESULTS FOR: {doc_type}")
        print("="*50)
        print(json.dumps(result["fields"], indent=2))
        print(f"\nNeeds Review: {result['needs_review']}")
        print(f"Notes: {result.get('notes', 'None')}")
        print("="*50 + "\n")
    else:
        logger.error("Extraction failed.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 test_extraction.py <path_to_file>")
    else:
        run_test_on_file(sys.argv[1])
