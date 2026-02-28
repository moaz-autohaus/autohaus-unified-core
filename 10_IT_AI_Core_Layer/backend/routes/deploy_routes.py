import os
import hmac
import hashlib
import logging
import subprocess
from fastapi import APIRouter, Request, HTTPException, Header, BackgroundTasks

logger = logging.getLogger("autohaus.deploy")
deploy_router = APIRouter()

def execute_git_pull():
    try:
        # Assuming the current working directory is inside the git repository
        logger.info("Executing git pull...")
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Git pull successful:\n{result.stdout}")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Git pull failed:\n{e.stderr}")
    except Exception as e:
        logger.error(f"Error executing git pull: {e}")

@deploy_router.post("/api/deploy/webhook")
async def github_webhook(
    request: Request, 
    background_tasks: BackgroundTasks, 
    x_hub_signature_256: str = Header(None)
):
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
    if not secret:
        logger.warning("[DEPLOY] GITHUB_WEBHOOK_SECRET is not set. Deployment cannot be secured.")
        raise HTTPException(status_code=500, detail="Deployment secret not configured on server")

    if not x_hub_signature_256:
        logger.warning("[DEPLOY] Missing X-Hub-Signature-256 header")
        raise HTTPException(status_code=401, detail="Missing signature")
        
    payload = await request.body()
    
    # Verify GitHub signature
    expected_signature = "sha256=" + hmac.new(
        secret.encode('utf-8'), payload, hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected_signature, x_hub_signature_256):
        logger.warning("[DEPLOY] Invalid signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    logger.info("[DEPLOY] GitHub webhook validated. Queuing git pull...")
    
    # Run in background so we return 200 to GitHub immediately
    background_tasks.add_task(execute_git_pull)
    
    return {"status": "success", "message": "Deployment triggered. Git pull initiated."}
