import os
import io
import sys
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

ROUTES_FOLDER_ID = '1G6jmMmGgzoOaSY5Ac4UfI8aGwHsAaW8P'
OUTPUT_DIR = '/Users/moazsial/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/backend/routes'

def download_routes():
    print(f"[DRIVE API] Accessing Routes Folder ID: {ROUTES_FOLDER_ID}...")
    try:
        credentials, project = google.auth.default(
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        service = build('drive', 'v3', credentials=credentials)
        
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        query = f"'{ROUTES_FOLDER_ID}' in parents and trashed = false"
        results = service.files().list(
            q=query, 
            fields="nextPageToken, files(id, name)",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True
        ).execute()
        items = results.get('files', [])

        if not items:
            print("[ERROR] No files found in the routes folder.")
            return False

        print(f"Found {len(items)} items.")
        
        success_count = 0
        for item in items:
            name = item['name']
            file_id = item['id']
            if name.endswith('.py'):
                print(f"[DOWNLOAD] Fetching {name} (ID: {file_id})...")
                request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
                out_path = os.path.join(OUTPUT_DIR, name)
                fh = io.FileIO(out_path, 'wb')
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                print(f"  -> Saved to {out_path}")
                success_count += 1

        print(f"[SUCCESS] Downloaded {success_count} python files to {OUTPUT_DIR}")
        return True

    except Exception as e:
        print(f"[CRITICAL FAILURE] Drive API Error: {str(e)}")
        return False

if __name__ == "__main__":
    if not download_routes():
        sys.exit(1)
