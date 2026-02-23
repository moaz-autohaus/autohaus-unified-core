import google.auth
from googleapiclient.discovery import build
import sys

def rename_drive_root():
    print("[RENAME] Authenticating as moaz@autohausia.com via DwD...")
    credentials, project = google.auth.default(scopes=['https://www.googleapis.com/auth/drive'])
    if hasattr(credentials, 'with_subject'):
        credentials = credentials.with_subject('moaz@autohausia.com')

    service = build('drive', 'v3', credentials=credentials)
    
    queries = [
        "name = 'AutoHaus_Unified_Data_Core' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        "name = 'AutoHaus_CIL_Root' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    ]
    
    folder_id = None
    folder_name = None
    for q in queries:
        results = service.files().list(q=q, spaces='drive', fields='files(id, name)').execute()
        items = results.get('files', [])
        if items:
            folder_id = items[0]['id']
            folder_name = items[0]['name']
            print(f"Found folder: {folder_name} (ID: {folder_id})")
            break
            
    if not folder_id:
        print("[SKIP] Could not find the legacy root folder to rename.")
        new_q = "name = 'AutoHaus_Unified_Data_Core' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        new_results = service.files().list(q=new_q, spaces='drive', fields='files(id, name)').execute()
        new_items = new_results.get('files', [])
        if new_items:
            print(f"[VERIFIED] Folder 'AutoHaus_Unified_Data_Core' already exists (ID: {new_items[0]['id']}).")
        return
        
    print(f"Renaming '{folder_name}' to 'AutoHaus_Unified_Data_Core'...")
    file_metadata = {'name': 'AutoHaus_Unified_Data_Core'}
    updated_file = service.files().update(fileId=folder_id, body=file_metadata, fields='id, name').execute()
    print(f"[SUCCESS] Renamed folder to {updated_file.get('name')}")

if __name__ == '__main__':
    rename_drive_root()
