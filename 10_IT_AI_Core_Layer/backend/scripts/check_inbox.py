
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

SA_KEY_PATH = "/Users/moazsial/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/backend/auth/replit-sa-key.json"
ECOSYSTEM_FOLDER_ID = '1YhWi3cCIO-qX8r0hbzxM0zaX-_u0T-TI'

def list_inbox():
    try:
        credentials = service_account.Credentials.from_service_account_file(SA_KEY_PATH)
        scoped_credentials = credentials.with_scopes(['https://www.googleapis.com/auth/drive.readonly'])
        service = build('drive', 'v3', credentials=scoped_credentials)

        # Find 00_Inbox
        results = service.files().list(
            q=f"'{ECOSYSTEM_FOLDER_ID}' in parents and name = '00_Inbox' and trashed = false",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            fields="files(id, name)"
        ).execute()
        
        inbox = results.get('files', [])
        if not inbox:
            print("00_Inbox folder not found.")
            return
            
        inbox_id = inbox[0]['id']
        print(f"Checking 00_Inbox ({inbox_id})...")
        
        results = service.files().list(
            q=f"'{inbox_id}' in parents and trashed = false",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            fields="files(id, name, mimeType)"
        ).execute()
        
        files = results.get('files', [])
        if not files:
            print("Inbox is empty.")
        else:
            for f in files:
                print(f"  - {f['name']} ({f['id']}) [{f['mimeType']}]")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_inbox()
