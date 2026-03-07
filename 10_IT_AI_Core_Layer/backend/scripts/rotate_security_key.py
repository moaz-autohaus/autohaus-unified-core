import os
import sys
import secrets
import bcrypt
import time
import logging
from datetime import datetime

# Add parent dir to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.rotation_utils import (
    create_new_version,
    disable_previous_versions,
    trigger_cloud_run_revision,
    write_rotation_event,
    send_confirmation_sms
)

logger = logging.getLogger("autohaus.rotate_security_key")
logging.basicConfig(level=logging.INFO)

SECRET_NAME = "SECURITY_ACCESS_KEY_HASH"

def rotate_security_key():
    """Strict flow for rotating the root security key."""
    
    # 1. Confirmation Gate
    print("-" * 60)
    print("WARNING: You are rotating the SECURITY_ACCESS_KEY_HASH.")
    print("This will break all active MCP sessions and invalidates current keys.")
    print("-" * 60)
    
    try:
        confirm = input("Type CONFIRM to proceed: ")
    except EOFError:
        print("\nRotation aborted. Non-interactive input or closed stream detected.")
        sys.exit(0)
    
    if confirm.strip() != "CONFIRM":
        print("Rotation aborted. Safety first.")
        sys.exit(0)

    # 2. Generate new 64-char hex token
    raw_token = secrets.token_hex(32) # 32 bytes = 64 hex chars
    
    # 3. Hash it (bcrypt)
    # The application uses this hash to verify incoming Bearer tokens
    salt = bcrypt.gensalt(rounds=12)
    token_hash = bcrypt.hashpw(raw_token.encode('utf-8'), salt).decode('utf-8')
    
    logger.info("Generated and hashed new security key using bcrypt (12 rounds).")

    # 4. Create new Secret Manager version
    version_num = create_new_version(SECRET_NAME, token_hash)
    
    # 5. Disable previous versions
    disable_previous_versions(SECRET_NAME, version_num)
    
    # 6. Trigger Cloud Run revision
    trigger_cloud_run_revision()
    
    # 7. Write SOVEREIGN audit event
    write_rotation_event(SECRET_NAME, "MOAZ_SIAL", mcp_invalidated=True)
    
    # 8. Deliver raw token
    sms_msg = f"SECURITY KEY ROTATED. New token: {raw_token}. Save to Apple Note now. This message will not be resent."
    send_confirmation_sms(sms_msg)
    
    print("\n" + "=" * 60)
    print("SECURITY KEY ROTATED SUCCESSFULLY")
    print(f"NEW TOKEN: {raw_token}")
    print("=" * 60)
    print("Save this token immediately. It will NOT be shown again.")
    print("Terminal will CLEAR and WIPE scrollback in 30 seconds.")
    print("=" * 60)
    
    # 9. Wait and Clear
    time.sleep(30)
    os.system('clear && printf "\\e[3J"')
    print("Terminal wiped. Rotation complete.")

if __name__ == "__main__":
    rotate_security_key()
