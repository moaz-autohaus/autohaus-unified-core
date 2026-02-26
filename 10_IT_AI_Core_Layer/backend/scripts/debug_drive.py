
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

SA_KEY_PATH = "/Users/moazsial/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/backend/auth/replit-sa-key.json"

def find_specific_folders():
    try:
        credentials = service_account.Credentials.from_service_account_file(SA_KEY_PATH)
        scoped_credentials = credentials.with_scopes(['https://www.googleapis.com/auth/drive.readonly'])
        service = build('drive', 'v3', credentials=scoped_credentials)

        search_terms = ['Title', 'Auction', 'Insurance', 'Compliance', 'Service', 'Transport', 'Finance', 'Sales']
        print(f"Searching for folders containing keywords: {search_terms}\n")
        
        for term in search_terms:
            query = f"name contains '{term}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            results = service.files().list(
                q=query,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                fields="files(id, name, parents)"
            ).execute()
            items = results.get('files', [])
            
            if items:
                print(f"--- Keyword: {term} ---")
                for item in items:
                    print(f"  - {item['name']} ({item['id']}) Parents: {item.get('parents')}")
            else:
                print(f"--- Keyword: {term} (No folders found) ---")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    find_specific_folders()
