import google.auth
from googleapiclient.discovery import build
import datetime
import sys

def execute_shadow_archive():
    SHARED_DRIVE_ID = '1YhWi3cCIO-qX8r0hbzxM0zaX-_u0T-TI' 
    print(f"[SHADOW ARCHIVE] Initializing targeted archive in Shared Drive: {SHARED_DRIVE_ID}...")
    
    try:
        credentials, project = google.auth.default(scopes=['https://www.googleapis.com/auth/drive'])
        service = build('drive', 'v3', credentials=credentials)
        
        # 1. Get top-level folders
        results = service.files().list(
            q=f"'{SHARED_DRIVE_ID}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            fields='files(id, name)'
        ).execute()
        
        top_folders = results.get('files', [])
        ARCHIVE_NAME = "_LEGACY_AUDIT_20260223"
        
        for folder in top_folders:
            folder_id = folder['id']
            folder_name = folder['name']
            
            # Skip the Inbox 
            if folder_name == 'Inbox':
                continue
                
            print(f"\\n[{folder_name}] Auditing...")
            
            # Search for anything inside this folder, excluding the archive folder itself
            items_query = f"'{folder_id}' in parents and trashed = false and name != '{ARCHIVE_NAME}'"
            items_results = service.files().list(
                q=items_query,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                fields='files(id, name)'
            ).execute()
            
            items = items_results.get('files', [])
            
            if not items:
                print(f"[{folder_name}] Root is already clean.")
                continue
                
            print(f"[{folder_name}] Found {len(items)} existing items. Creating Archive...")
            
            # Create Archive Folder
            archive_metadata = {
                'name': ARCHIVE_NAME,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [folder_id]
            }
            archive_folder = service.files().create(
                body=archive_metadata,
                supportsAllDrives=True,
                fields='id'
            ).execute()
            
            archive_id = archive_folder.get('id')
            
            # Move all items into the Archive
            for item in items:
                # Retrieve the existing parents to remove
                file_id = item['id']
                file = service.files().get(
                    fileId=file_id,
                    supportsAllDrives=True,
                    fields='parents'
                ).execute()
                previous_parents = ",".join(file.get('parents'))
                
                # Move the file
                service.files().update(
                    fileId=file_id,
                    addParents=archive_id,
                    removeParents=previous_parents,
                    supportsAllDrives=True,
                    fields='id, parents'
                ).execute()
                print(f"  -> Moved '{item['name']}' to {ARCHIVE_NAME}/")
                
            print(f"[{folder_name}] Archive Complete. Root is immaculate.")
            
        print("\\n[SHADOW ARCHIVE SUCCESS] All layers successfully archived.")
        
    except Exception as e:
        print(f"[CRITICAL ERROR] Archive Failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    execute_shadow_archive()
