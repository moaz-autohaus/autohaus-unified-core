
import os
import json
import logging
from google.cloud import bigquery
from google.oauth2 import service_account
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("credentials_check")

# Path to the key we found (updated to the backend/auth path where we just moved it)
SA_KEY_PATH = "/Users/moazsial/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/backend/auth/replit-sa-key.json"

def check_gemini():
    logger.info("Checking Gemini API...")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY is missing from environment.")
        return False
    
    try:
        genai.configure(api_key=api_key)
        # Using a model we saw in the list
        model_name = "gemini-flash-latest"
        logger.info(f"Using model: {model_name}")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Say 'Gemini OK' in one line.")
        logger.info(f"Gemini Response: {response.text.strip()}")
        return "Gemini OK" in response.text
    except Exception as e:
        logger.error(f"Gemini check failed: {e}")
        return False

def check_bigquery():
    logger.info("Checking BigQuery Connectivity...")
    project_id = "autohaus-infrastructure"
    
    if os.path.exists(SA_KEY_PATH):
        try:
            logger.info(f"Using key file: {SA_KEY_PATH}")
            credentials = service_account.Credentials.from_service_account_file(SA_KEY_PATH)
            client = bigquery.Client(credentials=credentials, project=project_id)
            datasets = list(client.list_datasets())
            logger.info(f"Found {len(datasets)} datasets in {project_id}")
            for d in datasets:
                logger.info(f"  - Dataset: {d.dataset_id}")
            return True
        except Exception as e:
            logger.error(f"BigQuery list_datasets failed with key file: {e}")
            return False
    else:
        logger.error(f"SA key file not found at {SA_KEY_PATH}")
        return False

if __name__ == "__main__":
    gemini_ok = check_gemini()
    bq_ok = check_bigquery()
    
    print("\n" + "="*30)
    print(f"Gemini Working:   {gemini_ok}")
    print(f"BigQuery Working: {bq_ok}")
    print("="*30)
