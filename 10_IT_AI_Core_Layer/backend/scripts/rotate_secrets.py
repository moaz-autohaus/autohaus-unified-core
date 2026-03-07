import os
import sys
import secrets
import argparse
import logging
from datetime import datetime

# Add parent dir to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.rotation_utils import (
    create_new_version,
    disable_previous_versions,
    trigger_cloud_run_revision,
    write_rotation_event,
    send_confirmation_sms,
    PROJECT_ID
)

# Standard tokens that can be generated via secrets.token_urlsafe(32)
GENERATABLE_SECRETS = [
    "GEMINI_API_KEY",
    "TWILIO_AUTH_TOKEN",
    "GITHUB_WEBHOOK_SECRET",
    "AUTOHAUS_MCP_TOKEN"
]

# Secrets that are externally provided (Moaz injects them)
EXTERNAL_SECRETS = [
    "TWILIO_ACCOUNT_SID",
    "GCP_SERVICE_ACCOUNT_JSON"
]

ALL_SECRETS = GENERATABLE_SECRETS + EXTERNAL_SECRETS

logger = logging.getLogger("autohaus.rotate_secrets")
logging.basicConfig(level=logging.INFO)

def rotate_secret(secret_name: str, dry_run: bool = False):
    """Executes the rotation flow for a single secret."""
    logger.info(f"Starting rotation for: {secret_name}")
    
    if secret_name not in ALL_SECRETS:
        raise ValueError(f"Secret {secret_name} is not in scope for standard rotation.")

    # 1. Generate (if applicable)
    new_value = None
    if secret_name in GENERATABLE_SECRETS:
        new_value = secrets.token_urlsafe(32)
        logger.info(f"Generated new value for {secret_name} (token_urlsafe).")
    else:
        # For external ones, we'd need a way to input them or they are just placeholders for manual rotation
        logger.warning(f"{secret_name} is an external secret. Manual injection required or special handling.")
        return

    if dry_run:
        logger.info(f"[DRY RUN] Generated new value for {secret_name}")
        logger.info(f"[DRY RUN] ACTION: Create new Secret Manager version for 'projects/{PROJECT_ID}/secrets/{secret_name}'")
        logger.info(f"[DRY RUN] ACTION: Disable all previous active versions of '{secret_name}'")
        logger.info(f"[DRY RUN] ACTION: Trigger Cloud Run revision for 'autohaus-cil' to pick up new version")
        logger.info(f"[DRY RUN] ACTION: Write 'CREDENTIAL_ROTATED' event to 'autohaus_cil.cil_events' in BigQuery")
        logger.info(f"[DRY RUN] ACTION: Print MANUAL STEP REQUIRED for Replit Secret '[name]'")
        logger.info(f"[DRY RUN] ACTION: Send confirmation SMS to MOAZ_SOVEREIGN via Twilio")
        return

    # 2. Create new Secret Manager version
    version_num = create_new_version(secret_name, new_value)
    
    # 3. Disable previous versions
    disable_previous_versions(secret_name, version_num)
    
    # 4. Trigger Cloud Run revision
    trigger_cloud_run_revision()
    
    # 5. Write audit event to cil_events
    write_rotation_event(secret_name, "MOAZ_SIAL")
    
    # 6. Send confirmation SMS
    sms_msg = f"ROTATION COMPLETE: {secret_name} (v{version_num}). Cloud Run revision triggered. Audit logged."
    send_confirmation_sms(sms_msg)
    
    print("\n" + "=" * 60)
    print(f"ROTATION SUCCESSFUL for {secret_name}")
    print(f"MANUAL STEP REQUIRED: Update Replit Secret '{secret_name}' with new value delivered via SMS.")
    print("=" * 60)
    
    logger.info(f"Successfully rotated {secret_name}")

def main():
    parser = argparse.ArgumentParser(description="AutoHaus C-OS Secret Rotation")
    parser.add_argument("--secret", help="Name of the specific secret to rotate")
    parser.add_argument("--all", action="store_true", help="Rotate all generatable secrets")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without executing")
    
    args = parser.parse_args()
    
    if args.all:
        for s in GENERATABLE_SECRETS:
            rotate_secret(s, args.dry_run)
    elif args.secret:
        rotate_secret(args.secret, args.dry_run)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
