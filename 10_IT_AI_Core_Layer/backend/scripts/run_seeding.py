"""
CLI script to run corpus seeding.
Usage:
  python -m scripts.run_seeding --dry-run              # Preview files
  python -m scripts.run_seeding --tiers 1 2             # Seed tiers 1 & 2 only
  python -m scripts.run_seeding                         # Seed all tiers
"""

import os
import sys
import json
import argparse
import logging

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("seeding_cli")


def main():
    parser = argparse.ArgumentParser(description="AutoHaus CIL Corpus Seeding")
    parser.add_argument("--dry-run", action="store_true", help="List files without processing")
    parser.add_argument("--tiers", nargs="+", type=int, help="Specific tiers to seed (e.g., 1 2 3)")
    parser.add_argument("--budget", type=float, default=50.0, help="Per-tier budget cap in USD")
    args = parser.parse_args()

    # Initialize clients
    from google.cloud import bigquery
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "auth", "replit-sa-key.json")
    sa_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")

    if os.path.exists(key_path):
        creds = service_account.Credentials.from_service_account_file(key_path)
    elif sa_json:
        creds = service_account.Credentials.from_service_account_info(json.loads(sa_json))
    else:
        logger.error("No GCP credentials found.")
        sys.exit(1)

    bq_client = bigquery.Client(credentials=creds, project="autohaus-infrastructure")
    drive_creds = creds.with_scopes(["https://www.googleapis.com/auth/drive"])
    drive_service = build("drive", "v3", credentials=drive_creds)

    # Update budget if specified
    from pipeline.seeding import SEEDING_CONFIG, run_seeding
    SEEDING_CONFIG["abort_threshold_usd"] = args.budget

    logger.info(f"Starting seeding. Dry run: {args.dry_run}. Tiers: {args.tiers or 'ALL'}. Budget: ${args.budget}")
    
    results = run_seeding(bq_client, drive_service, tiers=args.tiers, dry_run=args.dry_run)
    
    print("\n" + "=" * 60)
    print("SEEDING RESULTS")
    print("=" * 60)
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
