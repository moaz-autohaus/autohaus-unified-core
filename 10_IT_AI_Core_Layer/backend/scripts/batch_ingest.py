# backend/scripts/batch_ingest.py
# Idempotent: skips files that already have a PROPOSED or APPROVED hitl_events entry.
# Resilient: warm-up ping aborts if server is sleeping. Up to 2 retries on network exceptions.

import os
import sys
import httpx
import asyncio
from pathlib import Path

BASE_URL = os.getenv("CIL_BASE_URL", "http://localhost:5000")
DOCS_DIR = Path(os.getenv("DOCS_DIR", "10_IT_AI_Core_Layer/attached_assets"))
ACTOR_ID = "MOAZ_SIAL"
ACCESS_LEVEL = "SOVEREIGN"

SUPPORTED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png", ".docx", ".xlsx"]
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 10
INTER_FILE_SLEEP_SECONDS = 5


async def warm_up_ping(client: httpx.AsyncClient) -> bool:
    """
    Pings the server before the batch starts.
    Returns True if the server is alive, False if sleeping or unreachable.
    Aborts the batch immediately on failure — do not run against a sleeping server.
    """
    for endpoint in ["/api/health", "/"]:
        try:
            resp = await client.get(f"{BASE_URL}{endpoint}", timeout=10.0)
            if resp.status_code < 500:
                print(f"✓ Server is alive (GET {endpoint} → {resp.status_code})")
                return True
        except Exception:
            continue
    return False


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


async def ingest_file_with_retry(client: httpx.AsyncClient, filepath: Path):
    """
    Wraps ingest_file with up to MAX_RETRIES retries on network exception.
    HTTP errors (4xx/5xx) are NOT retried — they indicate real pipeline failures.
    Only connection-level exceptions (server sleeping, TCP reset, timeout) are retried.
    """
    last_exception = None
    for attempt in range(1 + MAX_RETRIES):
        try:
            return await ingest_file(client, filepath)
        except (httpx.ConnectError, httpx.RemoteProtocolError,
                httpx.ReadTimeout, httpx.ConnectTimeout, asyncio.TimeoutError) as e:
            last_exception = e
            if attempt < MAX_RETRIES:
                print(f"  ⚠ {filepath.name} → Network exception (attempt {attempt + 1}/{1 + MAX_RETRIES}): {e}")
                print(f"    Retrying in {RETRY_BACKOFF_SECONDS}s...")
                await asyncio.sleep(RETRY_BACKOFF_SECONDS)
            else:
                raise last_exception
        except Exception as e:
            # Non-network exception — do not retry
            raise e


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

    async with httpx.AsyncClient() as client:
        # --- WARM-UP PING ---
        print("Pinging server before batch start...")
        server_alive = await warm_up_ping(client)
        if not server_alive:
            print()
            print("✗ ABORT: Server is not responding.")
            print("  The Replit instance is sleeping or the URL is wrong.")
            print(f"  CIL_BASE_URL = {BASE_URL}")
            print("  Wake up the Replit server (hit Run, wait for WS LIVE) then re-run this script.")
            sys.exit(1)
        print()

        results = {"success": [], "failed": [], "skipped": []}

        for filepath in files:
            print(f"Ingesting: {filepath.name}")
            try:
                name, status, body = await ingest_file_with_retry(client, filepath)
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
                    # HTTP 4xx/5xx = real pipeline error, do not retry
                    print(f"  ✗ {name} → HTTP {status}: {body}")
                    results["failed"].append({"file": name, "status": status, "error": body})
            except Exception as e:
                print(f"  ✗ {filepath.name} → Exception after {MAX_RETRIES} retries: {e}")
                results["failed"].append({"file": filepath.name, "error": str(e)})

            # Pause between files to avoid Gemini API rate limits
            await asyncio.sleep(INTER_FILE_SLEEP_SECONDS)

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
