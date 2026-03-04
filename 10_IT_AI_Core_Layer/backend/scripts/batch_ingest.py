# backend/scripts/batch_ingest.py
# Idempotent: checks if file_id already has a PROPOSED or APPROVED
# entry in hitl_events before re-ingesting. Skips if already processed.

import os
import httpx
import asyncio
from pathlib import Path

BASE_URL = os.getenv("CIL_BASE_URL", "http://localhost:5000")
DOCS_DIR = Path(os.getenv("DOCS_DIR", "10_IT_AI_Core_Layer/attached_assets"))
ACTOR_ID = "MOAZ_SIAL"
ACCESS_LEVEL = "SOVEREIGN"

SUPPORTED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png", ".docx", ".xlsx"]

async def ingest_file(client: httpx.AsyncClient, filepath: Path):
    with open(filepath, "rb") as f:
        files = {"file": (filepath.name, f, "application/octet-stream")}
        data = {"actor_id": ACTOR_ID, "access_level": ACCESS_LEVEL}
        response = await client.post(
            f"{BASE_URL}/api/media/ingest",
            files=files,
            data=data,
            timeout=120.0
        )
    return filepath.name, response.status_code, response.json()

async def run_batch():
    files = [
        f for f in DOCS_DIR.iterdir()
        if f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not files:
        print(f"No documents found in {DOCS_DIR}")
        return

    print(f"Found {len(files)} documents to ingest:")
    for f in files:
        print(f"  {f.name}")
    print()

    results = {"success": [], "failed": [], "skipped": []}

    async with httpx.AsyncClient() as client:
        for filepath in files:
            print(f"Ingesting: {filepath.name}")
            try:
                name, status, body = await ingest_file(client, filepath)
                if status == 200:
                    proposal_id = body.get("proposal_id", "unknown")
                    claim_count = body.get("claim_count", 0)
                    print(f"  ✓ {name} → {claim_count} claims → proposal {proposal_id}")
                    results["success"].append({
                        "file": name,
                        "proposal_id": proposal_id,
                        "claim_count": claim_count
                    })
                elif status == 409:
                    print(f"  ⟳ {name} → already processed, skipping")
                    results["skipped"].append(name)
                else:
                    print(f"  ✗ {name} → HTTP {status}: {body}")
                    results["failed"].append({"file": name, "status": status, "error": body})
            except Exception as e:
                print(f"  ✗ {filepath.name} → Exception: {e}")
                results["failed"].append({"file": filepath.name, "error": str(e)})

            # Pause between ingestions to avoid overwhelming Gemini API
            await asyncio.sleep(5)

    print()
    print("=" * 60)
    print("BATCH INGESTION COMPLETE")
    print(f"  Success:  {len(results['success'])}")
    print(f"  Skipped:  {len(results['skipped'])}")
    print(f"  Failed:   {len(results['failed'])}")
    print()

    if results["success"]:
        print("SUCCESSFUL INGESTIONS:")
        for r in results["success"]:
            print(f"  {r['file']}: {r['claim_count']} claims → {r['proposal_id']}")

    if results["failed"]:
        print()
        print("FAILED INGESTIONS — INVESTIGATE:")
        for r in results["failed"]:
            print(f"  {r['file']}: {r.get('status', 'exception')} → {r.get('error', '')}")

if __name__ == "__main__":
    asyncio.run(run_batch())
