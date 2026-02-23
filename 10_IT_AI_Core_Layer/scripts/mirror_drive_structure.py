import os
import sys
import google.auth
from googleapiclient.discovery import build

IMPERSONATED_USER = 'moaz@autohausia.com'
DRIVE_ROOT_NAME = 'AutoHaus_CIL_Root'

LOCAL_LAYERS = [
    '01_Unified_Inbox',
    '02_Unified_Processed',
    '03_Personnel_Registry',
    '04_Unified_Projects',
    '05_AutoHaus_Businesses',
    '06_Unified_Finance',
    '07_Unified_Health',
    '08_Unified_Evidence',
    '09_Unified_Knowledge',
    '10_IT_AI_Core_Layer'
]

def get_or_create_folder(service, name, parent_id=None):
    query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    
    if items:
        return items[0]['id']
    else:
        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            file_metadata['parents'] = [parent_id]
            
        file = service.files().create(body=file_metadata, fields='id').execute()
        return file.get('id')

def mirror_layers():
    print(f"[DRIVE SYNC] Authenticating as {IMPERSONATED_USER} via DwD...")
    try:
        credentials, project = google.auth.default(
            scopes=['https://www.googleapis.com/auth/drive']
        )
        if hasattr(credentials, 'with_subject'):
            credentials = credentials.with_subject(IMPERSONATED_USER)
            
        service = build('drive', 'v3', credentials=credentials)
        
        # Create Root
        root_id = get_or_create_folder(service, DRIVE_ROOT_NAME)
        print(f"[SUCCESS] Drive Root '{DRIVE_ROOT_NAME}' ID: {root_id}")
        
        # Create Layers
        for layer in LOCAL_LAYERS:
            folder_id = get_or_create_folder(service, layer, root_id)
            print(f"  -> Synced Layer: {layer} (ID: {folder_id})")
            
        return root_id
    except Exception as e:
        print(f"[CRITICAL FAILURE] Drive Mirror Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    mirror_layers()
