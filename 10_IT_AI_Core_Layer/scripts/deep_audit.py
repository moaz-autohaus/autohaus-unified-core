import google.auth
from googleapiclient.discovery import build
import json
import sys
import datetime

def audit_legacy_data():
    SHARED_DRIVE_ID = '1YhWi3cCIO-qX8r0hbzxM0zaX-_u0T-TI'  # AUTOHAUS_ECOSYSTEM
    print(f"[AUDIT] Deep Scanning Shared Drive ID: {SHARED_DRIVE_ID}...")
    
    try:
        credentials, project = google.auth.default(scopes=['https://www.googleapis.com/auth/drive.readonly'])
        service = build('drive', 'v3', credentials=credentials)
        
        # 1. Get top-level folders
        results = service.files().list(
            q=f"'{SHARED_DRIVE_ID}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            fields='files(id, name)'
        ).execute()
        
        top_folders = results.get('files', [])
        
        audit_report = "# Legacy Data Audit Report\\n\\n"
        
        for folder in top_folders:
            folder_id = folder['id']
            folder_name = folder['name']
            
            # Recursively get files inside this folder
            query = f"'{folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed = false"
            files_results = service.files().list(
                q=query,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                fields='files(id, name, modifiedTime)'
            ).execute()
            
            files = files_results.get('files', [])
            
            file_count = len(files)
            most_recent_file = "None"
            most_recent_time = ""
            
            if file_count > 0:
                # Sort by modifiedTime descending
                files.sort(key=lambda x: x.get('modifiedTime', ''), reverse=True)
                most_recent_file = files[0]['name']
                most_recent_time = files[0]['modifiedTime']
                
            audit_report += f"## {folder_name}\\n"
            audit_report += f"- **Total file count:** {file_count}\\n"
            audit_report += f"- **Most Recent file:** {most_recent_file} ({most_recent_time})\\n\\n"
            
            # Subfolders check
            sub_query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            sub_results = service.files().list(
                q=sub_query,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                fields='files(id, name)'
            ).execute()
            subfolders = sub_results.get('files', [])
            if subfolders:
                audit_report += f"- **Subfolders found:** {', '.join([sf['name'] for sf in subfolders])}\\n\\n"
            
        print(audit_report)
        
        with open("Legacy_Data_Audit.md", "w") as f:
            f.write(audit_report)
            
        print("[SUCCESS] Wrote Legacy_Data_Audit.md")
        
    except Exception as e:
        print(f"[CRITICAL ERROR] Drive Audit Failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    audit_legacy_data()
