import os
import subprocess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("replit-deploy")

def force_sync():
    """
    Manually triggers a git pull from the Replit environment.
    Use this if the automated sync or webhook is stuck.
    """
    try:
        # 1. Determine root (one level up from scripts/ in backend context)
        cwd = os.getcwd()
        logger.info(f"Current working directory: {cwd}")
        
        # 2. Execute git pull
        logger.info("Executing git pull origin main...")
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info(f"SYNC SUCCESSFUL:\n{result.stdout}")
        
        # 3. Instruction to restart server
        logger.info("---")
        logger.info("Next Step: Restart your Replit server to load the new hitl_routes.py logic.")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"SYNC FAILED:\n{e.stderr}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    force_sync()
