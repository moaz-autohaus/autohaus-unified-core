import os
import httpx
from fastapi import APIRouter, Request, HTTPException

webhook_router = APIRouter()

# --- Relay Infrastructure ---
async def send_to_ingestion_layer(payload_type: str, data: dict):
    webhook_url = os.environ.get("CIL_WEBHOOK_URL")
    if not webhook_url:
        print("[ERROR] CIL_WEBHOOK_URL is not set.")
        return {"status": "Error. Webhook URL missing."}

    payload = {
        "type": payload_type,
        "data": data
    }

    print(f"[RELAY] Forwarding '{payload_type}' to Unified Webhook: {webhook_url}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload, timeout=10.0)
            response.raise_for_status()
            return {"status": "Success", "response": response.json()}
    except Exception as e:
        print(f"[ERROR] Failed to forward payload: {e}")
        return {"status": "Error", "detail": str(e)}


@webhook_router.post("/leads")
async def process_lead(request: Request):
    """Forward Lead Capture Payload securely."""
    try:
        data = await request.json()
        await send_to_ingestion_layer("Trade-in / Lead Payload", data)
        return {"relay": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid Stateless Payload")


@webhook_router.post("/appointments")
async def process_book(request: Request):
    """Forward Service Schedule Action."""
    try:
        data = await request.json()
        await send_to_ingestion_layer("Service Booking Payload", data)
        return {"relay": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid Stateless Payload")
