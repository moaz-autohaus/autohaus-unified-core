
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

SA_KEY_PATH = "/Users/moazsial/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/backend/auth/replit-sa-key.json"

def inspect_folders():
    try:
        credentials = service_account.Credentials.from_service_account_file(SA_KEY_PATH)
        scoped_credentials = credentials.with_scopes(['https://www.googleapis.com/auth/drive.readonly'])
        service = build('drive', 'v3', credentials=scoped_credentials)

        folders_to_check = [
            {'name': '01_Admin_Legal', 'id': '19cSeBP9ZaR22OdXGLF0mMM0KZs2YkTb-'},
            {'name': '03_Dealership_KAMM', 'id': '1ybkJ-j65PEuZgtvdoQmR3Rv_Jqrrztte'}
        ]

        for f in folders_to_check:
            print(f"\n--- Inspecting {f['name']} ({f['id']}) ---")
            results = service.files().list(
                q=f"'{f['id']}' in parents and trashed = false",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                fields="files(id, name, mimeType)"
            ).execute()
            items = results.get('files', [])
            if not items:
                print("No active items found.")
            for item in items:
                print(f"  - {item['name']} [{item['mimeType']}]")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_folders()
