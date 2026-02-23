import os
import sys
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

IMPERSONATED_USER = 'moaz@autohausia.com'
DRIVE_ROOT_NAME = 'AutoHaus_Unified_Data_Core'
TARGET_LAYER = '05_AutoHaus_Businesses'
LOCAL_ASSETS_DIR = os.path.expanduser('~/Documents/AutoHaus_CIL/05_AutoHaus_Businesses')

def get_folder_id(service, name, parent_id=None):
    query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    return items[0]['id'] if items else None

def deploy_assets():
    print(f"[ASSET DEPLOY] Authenticating as {IMPERSONATED_USER} via DwD...")
    try:
        credentials, project = google.auth.default(scopes=['https://www.googleapis.com/auth/drive'])
        if hasattr(credentials, 'with_subject'):
            credentials = credentials.with_subject(IMPERSONATED_USER)
            
        service = build('drive', 'v3', credentials=credentials)
        
        # Find Root
        root_id = get_folder_id(service, DRIVE_ROOT_NAME)
        if not root_id:
            print(f"[ERROR] Could not find root folder '{DRIVE_ROOT_NAME}'")
            return

        # Find Layer 05
        layer_id = get_folder_id(service, TARGET_LAYER, root_id)
        if not layer_id:
            print(f"[ERROR] Could not find layer folder '{TARGET_LAYER}'")
            return
            
        print(f"-> Found Target Layer ID: {layer_id}")
        
        # Traverse local assets directory
        for root, dirs, files in os.walk(LOCAL_ASSETS_DIR):
            for filename in files:
                if filename == ".DS_Store":
                    continue
                    
                local_path = os.path.join(root, filename)
                print(f"Deploying asset: {filename}...")
                
                # Check if it already exists (simplistic check)
                query = f"name = '{filename}' and '{layer_id}' in parents and trashed = false"
                existing = service.files().list(q=query, fields="files(id)").execute().get("files", [])
                
                media = MediaFileUpload(local_path, resumable=True)
                if existing:
                    file_id = existing[0]['id']
                    service.files().update(fileId=file_id, media_body=media).execute()
                    print(f"  -> Updated existing file ID {file_id}")
                else:
                    file_metadata = {'name': filename, 'parents': [layer_id]}
                    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                    print(f"  -> Created new file ID {file.get('id')}")

        print("=== ASSET DEPLOYMENT COMPLETE ===")

    except Exception as e:
        print(f"[CRITICAL FAILURE] Asset Deploy Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    deploy_assets()
