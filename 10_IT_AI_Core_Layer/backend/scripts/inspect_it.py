
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

SA_KEY_PATH = "/Users/moazsial/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/backend/auth/replit-sa-key.json"

def inspect_it_layer():
    try:
        credentials = service_account.Credentials.from_service_account_file(SA_KEY_PATH)
        scoped_credentials = credentials.with_scopes(['https://www.googleapis.com/auth/drive.readonly'])
        service = build('drive', 'v3', credentials=scoped_credentials)

        fid = '1LnrWuTFyHGnUjH1zANu0zXM6IduJQdKp' # 10_IT_AI_Layer
        print(f"\n--- Inspecting 10_IT_AI_Layer ({fid}) ---")
        results = service.files().list(
            q=f"'{fid}' in parents and trashed = false",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            fields="files(id, name, mimeType)"
        ).execute()
        items = results.get('files', [])
        for item in items:
            print(f"  - {item['name']} [{item['mimeType']}]")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_it_layer()
