import functions_framework
import base64
import json
import os
import io
from google.cloud import bigquery
from googleapiclient.discovery import build
import google.auth
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel, Part, SafetySetting, FinishReason
import vertexai

# Initialize clients globally for reuse
try:
    credentials, project_id = google.auth.default()
    bq_client = bigquery.Client()
    drive_service = build('drive', 'v3', credentials=credentials)
    vertexai.init(project=project_id, location="us-central1")
except Exception as e:
    print(f"Error initializing clients: {e}")

MODEL_ID = "gemini-1.5-pro-preview-0409" # Using 1.5 Pro as 3.1 Pro equivalent for GCP Vertex
DATASET_ID = "autohaus_unified_core"
TABLE_ID = "dim_vehicles"

EXTRACTION_PROMPT = """
You are the Autohaus Unified Intelligence Layer.
Extract the following exact fields from the provided document.
Output valid JSON only, with no markdown formatting or explanation.
Keys:
  "vin" (string or null)
  "year" (integer or null)
  "make" (string or null)
  "model" (string or null)
  "purchase_price" (float or null)
  "vendor" (string or null)
"""

def extract_data_with_gemini(file_bytes, mime_type):
    try:
        model = GenerativeModel(MODEL_ID)
        document = Part.from_data(data=file_bytes, mime_type=mime_type)
        response = model.generate_content(
            [EXTRACTION_PROMPT, document],
            generation_config={
                "temperature": 0.1, # Extremely deterministic 
                "response_mime_type": "application/json",
            }
        )
        if response.text:
            return json.loads(response.text)
        return {}
    except Exception as e:
        print(f"Gemini Extraction Error: {e}")
        return {}

def insert_into_bq(extracted_data, file_link):
    table_ref = f"{bq_client.project}.{DATASET_ID}.{TABLE_ID}"
    
    row_to_insert = {
         "vin": extracted_data.get("vin"),
         "year": extracted_data.get("year"),
         "make": extracted_data.get("make"),
         "model": extracted_data.get("model"),
         "purchase_price": extracted_data.get("purchase_price"),
         "purchase_vendor": extracted_data.get("vendor"),
         "source_document_link": file_link,
         "is_governed": False,
         "current_status": 'DRAFT'
    }
    
    # Simple validation
    if not row_to_insert["vin"]:
         print("No VIN extracted, skipping BQ insert.")
         return False
         
    errors = bq_client.insert_rows_json(table_ref, [row_to_insert])
    if errors == []:
        print(f"Successfully inserted into BigQuery: {row_to_insert}")
        return True
    else:
        print(f"Encountered errors while inserting rows: {errors}")
        return False

@functions_framework.cloud_event
def unified_intake_trigger(cloud_event):
    """Triggered by a change to a Cloud Storage bucket or Pub/Sub."""
    print(f"Received event: {cloud_event.data}")
    
    # In a real Drive trigger, we'd receive a notification and need to fetch the file ID.
    # We will simulate the payload structure for direct testing via HTTP or PubSub containing the File ID
    
    try:
        data = base64.b64decode(cloud_event.data["message"]["data"]).decode()
        event_payload = json.loads(data)
        file_id = event_payload.get('fileId')
        
        if not file_id:
             print("No fileId found in payload")
             return
             
        # 1. Fetch File Metadata & Bytes
        file_meta = drive_service.files().get(fileId=file_id, supportsAllDrives=True, fields="id, name, mimeType, webViewLink").execute()
        print(f"Processing File: {file_meta.get('name')}")
        
        request = drive_service.files().get_media(fileId=file_id)
        file_bytes = request.execute()
        
        # 2. Extract Data via Gemini
        extracted_data = extract_data_with_gemini(file_bytes, file_meta.get('mimeType'))
        print(f"Extracted Data: {extracted_data}")
        
        # 3. Write to BigQuery Handshake
        insert_into_bq(extracted_data, file_meta.get('webViewLink'))
        
    except Exception as e:
        print(f"Function Error: {e}")
