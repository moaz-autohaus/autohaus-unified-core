
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

SA_KEY_PATH = "/Users/moazsial/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/backend/auth/replit-sa-key.json"
SHARED_DRIVE_ID = '1YhWi3cCIO-qX8r0hbzxM0zaX-_u0T-TI'

def get_drive_name():
    if not os.path.exists(SA_KEY_PATH):
        print(f"Error: {SA_KEY_PATH} not found.")
        return

    try:
        credentials = service_account.Credentials.from_service_account_file(SA_KEY_PATH)
        scoped_credentials = credentials.with_scopes(['https://www.googleapis.com/auth/drive.readonly'])
        service = build('drive', 'v3', credentials=scoped_credentials)

        print(f"Fetching metadata for Shared Drive ID: {SHARED_DRIVE_ID}")
        drive = service.drives().get(driveId=SHARED_DRIVE_ID).execute()
        print(f"Shared Drive Name: {drive.get('name')}")

    except Exception as e:
        print(f"An error occurred: {e}")
        print("Note: The service account likely doesn't have permission to see this drive yet.")

if __name__ == "__main__":
    get_drive_name()
