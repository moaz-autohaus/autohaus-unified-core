import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from routes.inventory import inventory_router
from routes.webhooks import webhook_router
from routes.chat_stream import chat_router
from routes.twilio_webhooks import twilio_router
from routes.quote_routes import quote_router
from routes.logistics import logistics_router
from routes.crm_intake import crm_router

app = FastAPI(title="AutoHaus CIL Bridge - Unified")

# API Routing
app.include_router(inventory_router, prefix="/api/inventory")
app.include_router(webhook_router, prefix="/api")
app.include_router(chat_router)  # WebSocket at /ws/chat (no prefix — WS routes are absolute)
app.include_router(twilio_router, prefix="/api")  # Twilio SMS at /api/webhooks/twilio/sms
app.include_router(quote_router, prefix="/api")   # Quote Portal at /api/public/quote/{uuid}
app.include_router(logistics_router, prefix="/api/logistics")
app.include_router(crm_router, prefix="/api/crm")


# Governance Anchor Path
@app.get("/api/heartbeat")
async def get_heartbeat():
    """Returns the pulse of the Core Backend to prevent the Kill Switch trigger."""
    return {"status": "alive", "cil_connection": "verified"}

# Static Hosting for React Frontend
# Points upward past `10_IT_AI_Core_Layer/backend` to the workspace root `dist/` directory
DIST_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "dist")

if os.path.exists(DIST_DIR):
    assets_dir = os.path.join(DIST_DIR, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

# Content Governance / Admin Gate
@app.api_route("/api/admin/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def catch_admin(request: Request, path: str):
    """
    Enforces the Administrative Lockout for non-CIL entities.
    Static redirects and governance overrides handled via Carbon LLC Orchestrator.
    """
    raise HTTPException(
        status_code=403, 
        detail="Governance Lockout: Administrative access restricted to autohausia.com Super Admin."
    )

# Fallback SPA Router
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    index_path = os.path.join(DIST_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse(
        status_code=404, 
        content={"message": "Frontend UI framework initializing. Stateless deployment pending."}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
