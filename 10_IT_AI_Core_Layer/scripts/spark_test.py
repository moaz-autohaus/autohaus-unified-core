import os
import sys
import datetime
import google.auth
from googleapiclient.discovery import build
from google.cloud import bigquery

# AutoHaus Unified Infrastructure: Spark Test (v2.4)
# Verifies DwD Handshake and Infrastructure Vision

PROJECT_ID = "autohaus-infrastructure"
IMPERSONATED_USER = "moaz@autohausia.com"
FOLDER_NAME = "01_Unified_Inbox"

def run_spark_test():
    print(f"[SPARK] Initiating Infrastructure Handshake for: {IMPERSONATED_USER}")
    
    try:
        # 1. Authenticate with DwD
        credentials, project = google.auth.default(
            scopes=[
                'https://www.googleapis.com/auth/drive',
                'https://www.googleapis.com/auth/cloud-platform',
                'https://www.googleapis.com/auth/bigquery'
            ]
        )
        
        if hasattr(credentials, 'with_subject'):
            credentials = credentials.with_subject(IMPERSONATED_USER)
            print("[SPARK] Domain-Wide Delegation: Impersonation Active.")
        else:
            print("[WARNING] Credentials missing 'with_subject' capability (ADC may be User-Auth).")

        # 2. Drive Search: Locate Unified_Inbox
        drive_service = build('drive', 'v3', credentials=credentials)
        query = f"name = '{FOLDER_NAME}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        items = results.get('files', [])

        if not items:
            print(f"[ERROR] '{FOLDER_NAME}' not found.")
            return False

        folder_id = items[0]['id']
        print(f"[SUCCESS] Located '{FOLDER_NAME}' (ID: {folder_id})")

        # 3. Create Test File
        file_metadata = {
            'name': 'connection_test_success.txt',
            'parents': [folder_id]
        }
        file_body = f"CIL Heartbeat: {datetime.datetime.now()}\nStatus: DwD Handshake Verified."
        
        # Use simple upload
        from googleapiclient.http import MediaInMemoryUpload
        media = MediaInMemoryUpload(file_body.encode('utf-8'), mimetype='text/plain')
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"[SUCCESS] Created test file: connection_test_success.txt (ID: {file.get('id')})")

        # 4. BigQuery Heartbeat
        bq_client = bigquery.Client(credentials=credentials, project=PROJECT_ID)
        query = f"""
            INSERT INTO `{PROJECT_ID}.autohaus_cil.audit_log` (timestamp, event, operator_id, run_id)
            VALUES (CURRENT_TIMESTAMP(), 'CIL_SPARK_TEST', 'autohaus-drive-bot', 'SPARK_{datetime.datetime.now().strftime('%Y%m%d')}')
        """
        query_job = bq_client.query(query)
        query_job.result() # Wait for completion
        print("[SUCCESS] BigQuery Heartbeat Logged.")
        
        return True

    except Exception as e:
        print(f"[CRITICAL] Spark Test Failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = run_spark_test()
    if not success:
        sys.exit(1)
