import os
import sys
import json
import uuid
import datetime
import requests
import subprocess
import google.auth
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

LOCAL_ROOT = os.path.expanduser('~/Documents/AutoHaus_CIL/01_Unified_Inbox')
LOCAL_REPO = os.path.expanduser('~/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer')

def get_cloud_run_url():
    try:
        result = subprocess.run(
            ["gcloud", "run", "services", "describe", "autohaus-cil-webhook", 
             "--platform", "managed", "--region", "us-central1", 
             "--format", "value(status.url)"],
            capture_output=True, text=True, check=True
        )
        base_url = result.stdout.strip()
        return base_url, base_url + "/webhook/intake"
    except Exception as e:
        print(f"[ERROR] Could not fetch Cloud Run URL: {e}")
        return None, None

def get_identity_token(audience):
    try:
        # Use gcloud to fetch the print-identity-token by impersonating the DwD bot
        result = subprocess.run(
            ["gcloud", "auth", "print-identity-token", 
             "--impersonate-service-account=autohaus-drive-bot@autohaus-infrastructure.iam.gserviceaccount.com",
             "--include-email",
             f"--audiences={audience}"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to obtain identity token via gcloud: {e.stderr}")
        return None

def main():
    print("=== STARTING UNIFIED HEARTBEAT TEST ===")
    
    # 1. Create Local File
    scan_id = uuid.uuid4().hex[:8]
    timestamp = datetime.datetime.now().isoformat()
    payload = {
        "event": "HEARTBEAT_TEST",
        "scan_id": scan_id,
        "timestamp": timestamp,
        "operator_id": "moaz@autohausia.com"
    }
    
    local_file = os.path.join(LOCAL_ROOT, f"heartbeat_{scan_id}.json")
    with open(local_file, 'w') as f:
        json.dump(payload, f)
    print(f"[1] Local file created: {local_file}")
    
    # 2. Sync to Drive
    print(f"[2] Syncing to Google Drive via DwD...")
    try:
        credentials, project = google.auth.default(scopes=['https://www.googleapis.com/auth/drive'])
        if hasattr(credentials, 'with_subject'):
            credentials = credentials.with_subject('moaz@autohausia.com')
        service = build('drive', 'v3', credentials=credentials)
        
        query = "name = '01_Unified_Inbox' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        items = results.get('files', [])
        
        if not items:
            print("[ERROR] Drive folder 01_Unified_Inbox not found.")
            sys.exit(1)
            
        folder_id = items[0]['id']
        file_metadata = {'name': f"heartbeat_{scan_id}.json", 'parents': [folder_id]}
        media = MediaFileUpload(local_file, mimetype='application/json')
        drive_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"    -> Synced to Drive ID: {drive_file.get('id')}")
        
    except Exception as e:
        print(f"[ERROR] Drive Sync Failed: {e}")
        sys.exit(1)
        
    # 3. Trigger Webhook
    print(f"[3] Triggering Cloud Run Webhook with OIDC Auth...")
    base_url, webhook_url = get_cloud_run_url()
    if not webhook_url:
        sys.exit(1)
        
    token = get_identity_token(base_url)
    if not token:
        sys.exit(1)
        
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    import time
    max_retries = 6
    for attempt in range(max_retries):
        try:
            response = requests.post(webhook_url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            run_id = data.get("run_id", "UNKNOWN")
            print(f"    -> Webhook Success! BQ Run ID: {run_id}")
            break
        except Exception as e:
            if response is not None and response.status_code == 403:
                print(f"    -> [Attempt {attempt+1}/{max_retries}] 403 Forbidden (IAM propagating...), retrying in 10s...")
                time.sleep(10)
            else:
                print(f"[ERROR] Webhook Trigger Failed: {e}")
                if 'response' in locals() and response is not None:
                    print(response.text)
                sys.exit(1)
    else:
        print("[ERROR] Max retries reached. Webhook Trigger Failed due to persistent 403.")
        sys.exit(1)
        
    # 4. Commit to GitHub
    print(f"[4] Committing log entry to GitHub...")
    try:
        log_file = os.path.join(LOCAL_REPO, "test_logs.txt")
        with open(log_file, "a") as f:
            f.write(f"{timestamp} | {scan_id} | {run_id} | UNIFIED ACTIVE\n")
            
        subprocess.run(["git", "add", "test_logs.txt"], cwd=LOCAL_REPO, check=True)
        subprocess.run(["git", "commit", "-m", f"Audit Log: {run_id}"], cwd=LOCAL_REPO, check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=LOCAL_REPO, check=True)
        print(f"    -> Log committed and pushed.")
    except Exception as e:
        print(f"[ERROR] GitHub Commit Failed: {e}")
        sys.exit(1)
        
    print("=== UNIFIED ALIGNMENT VERIFIED ===")

if __name__ == "__main__":
    main()
