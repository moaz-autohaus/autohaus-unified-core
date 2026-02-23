import google.auth
from googleapiclient.discovery import build
import json
import sys

def audit_shared_drive():
    SHARED_DRIVE_ID = '1YhWi3cCIO-qX8r0hbzxM0zaX-_u0T-TI'
    print(f"[AUDIT] Scanning Shared Drive ID: {SHARED_DRIVE_ID} via DwD...")
    
    try:
        credentials, project = google.auth.default(scopes=['https://www.googleapis.com/auth/drive.readonly'])

        service = build('drive', 'v3', credentials=credentials)
        
        # Query top-level items in the Shared Drive
        # driveId must be specified along with corpora='drive' and includeItemsFromAllDrives=True
        results = service.files().list(
            q=f"'{SHARED_DRIVE_ID}' in parents and trashed = false",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            fields='files(id, name, mimeType)'
        ).execute()
        
        items = results.get('files', [])
        
        if not items:
            print("The Shared Drive is currently empty.")
            return

        print("\n--- Top-Level Structure ---")
        folders = []
        files = []
        for item in items:
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                folders.append(item['name'])
                print(f"[FOLDER] {item['name']}")
            else:
                files.append(item['name'])
                print(f"[FILE] {item['name']}")
                
        print("\n[SUMMARY]")
        print(f"Total Folders: {len(folders)}")
        print(f"Total Files: {len(files)}")
        
    except Exception as e:
        print(f"[CRITICAL ERROR] Drive Audit Failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    audit_shared_drive()
