from google.cloud import secretmanager
import os

try:
    client = secretmanager.SecretManagerServiceClient()
    project_id = "autohaus-infrastructure"
    parent = f"projects/{project_id}"
    
    print("Checking Secret Manager...")
    secrets = client.list_secrets(request={"parent": parent})
    
    for secret in secrets:
        print(f"Found secret: {secret.name.split('/')[-1]}")
except Exception as e:
    print(f"Error accessing Secret Manager: {e}")
