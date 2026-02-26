
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

SA_KEY_PATH = "/Users/moazsial/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/backend/auth/replit-sa-key.json"
ECOSYSTEM_FOLDER_ID = '1YhWi3cCIO-qX8r0hbzxM0zaX-_u0T-TI'

TARGET_STRUCTURE = [
    "00_Inbox",
    "02_Titles",
    "03_Sales",
    "04_Insurance",
    "05_Service",
    "06_Auctions",
    "07_Transport",
    "08_Compliance",
    "10_Finance"
]

def force_restructure():
    try:
        credentials = service_account.Credentials.from_service_account_file(SA_KEY_PATH)
        scoped_credentials = credentials.with_scopes(['https://www.googleapis.com/auth/drive'])
        service = build('drive', 'v3', credentials=scoped_credentials)

        # 1. List current items
        print(f"Cleaning up AUTOHAUS_ECOSYSTEM ({ECOSYSTEM_FOLDER_ID})...")
        results = service.files().list(
            q=f"'{ECOSYSTEM_FOLDER_ID}' in parents and trashed = false",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            fields="files(id, name, mimeType)"
        ).execute()
        current_items = results.get('files', [])

        # 2. Cleanup loop
        for item in current_items:
            name = item['name']
            if name in TARGET_STRUCTURE:
                print(f"  - Keeping new structure folder: {name}")
                continue
            
            try:
                print(f"  - Deleting legacy item: {name} ({item['id']})...")
                service.files().delete(fileId=item['id'], supportsAllDrives=True).execute()
            except Exception as e:
                print(f"    ❌ Error deleting {name}: {e}")

        # 3. Verify / Create target folders
        print("\nVerifying final structure...")
        results = service.files().list(
            q=f"'{ECOSYSTEM_FOLDER_ID}' in parents and trashed = false",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            fields="files(id, name)"
        ).execute()
        existing_names = [i['name'] for i in results.get('files', [])]

        for folder_name in TARGET_STRUCTURE:
            if folder_name not in existing_names:
                print(f"  - Creating missing folder: {folder_name}...")
                folder_metadata = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [ECOSYSTEM_FOLDER_ID]
                }
                service.files().create(body=folder_metadata, supportsAllDrives=True).execute()
            else:
                print(f"  - {folder_name} is active.")

        print("\n✅ Drive environment is now clean and restructured for CIL.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    force_restructure()
