
import os
import logging
import bcrypt
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Request, HTTPException, Depends, Header, Query
from google.cloud import bigquery
from database.bigquery_client import BigQueryClient
from database.policy_engine import get_policy
from pydantic import BaseModel

logger = logging.getLogger("autohaus.security")

# Router setup
security_router = APIRouter(prefix="/api/security", tags=["security"])

# ───────────────────────────────────────────────────────────────────────────────
# Authentication Middleware
# ───────────────────────────────────────────────────────────────────────────────

def verify_security_access(authorization: Optional[str] = Header(None)):
    """
    Validates Bearer token against bcrypt hash in environment.
    Returns 404 (Not Found) on any failure to remain silent/invisible.
    """
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning(f"[SECURITY] Unauthorized access attempt (missing/invalid header)")
        raise HTTPException(status_code=404)
    
    token = authorization.replace("Bearer ", "")
    access_key_hash = os.environ.get("SECURITY_ACCESS_KEY_HASH")
    
    if not access_key_hash:
        logger.error("[SECURITY] SECURITY_ACCESS_KEY_HASH not set in environment.")
        raise HTTPException(status_code=404)
    
    try:
        # Verify against bcrypt hash
        if not bcrypt.checkpw(token.encode('utf-8'), access_key_hash.encode('utf-8')):
             logger.warning(f"[SECURITY] Invalid key attempt.")
             raise HTTPException(status_code=404)
    except Exception as e:
        logger.error(f"[SECURITY] Key verification error: {e}")
        raise HTTPException(status_code=404)

    return True

def log_security_action(request: Request, action: str, result: str):
    """Logs action to isolated security_access_log table."""
    bq = BigQueryClient()
    now = datetime.utcnow().isoformat()
    ip = request.client.host if request.client else "unknown"
    
    log_row = {
        "timestamp": now,
        "action": action,
        "ip_address": ip,
        "result": result
    }
    
    try:
        # We try to insert to the isolated log table
        dataset = os.environ.get("BQ_DATASET", "autohaus_cil")
        project = os.environ.get("GCP_PROJECT", "autohaus-infrastructure")
        table_id = f"{project}.{dataset}.security_access_log"
        
        errors = bq.client.insert_rows_json(table_id, [log_row])
        if errors:
            logger.error(f"[SECURITY AUDIT] Log insertion failed: {errors}")
    except Exception as e:
        logger.error(f"[SECURITY AUDIT] Log failed: {e}")

# ───────────────────────────────────────────────────────────────────────────────
# Read Endpoints
# ───────────────────────────────────────────────────────────────────────────────

@security_router.get("/state", dependencies=[Depends(verify_security_access)])
async def get_system_state(request: Request):
    """Compressed read-only view of entire CIL state."""
    bq = BigQueryClient()
    
    # 1. Health / Primitives (Simulated for skeleton)
    state = {
        "status": "OPERATIONAL",
        "timestamp": datetime.utcnow().isoformat(),
        "freeze_status": get_policy("SYSTEM", "FROZEN") or False,
        "active_threads": 42, # Placeholder
        "service_versions": {
            "core": "1.2.0",
            "extraction": "2.1.0",
            "financial": "1.0.5"
        }
    }
    
    # 2. Key Metrics
    try:
        inventory_count = list(bq.client.query("SELECT COUNT(*) as cnt FROM `autohaus-infrastructure.autohaus_cil.inventory`").result())[0].cnt
        lead_count = list(bq.client.query("SELECT COUNT(*) as cnt FROM `autohaus-infrastructure.autohaus_cil.leads`").result())[0].cnt
        hitl_queue_count = list(bq.client.query("SELECT COUNT(*) as cnt FROM `autohaus-infrastructure.autohaus_cil.hitl_events` WHERE status = 'PROPOSED'").result())[0].cnt
        
        state["metrics"] = {
            "total_inventory": inventory_count,
            "active_leads": lead_count,
            "pending_proposals": hitl_queue_count
        }
    except Exception as e:
        state["metrics_error"] = str(e)

    log_security_action(request, "GET_STATE", "SUCCESS")
    return state

@security_router.get("/events", dependencies=[Depends(verify_security_access)])
async def get_events(request: Request, since: Optional[str] = Query(None)):
    """Unfiltered cil_events stream."""
    bq = BigQueryClient()
    query = "SELECT * FROM `autohaus-infrastructure.autohaus_cil.cil_events`"
    if since:
        query += f" WHERE timestamp > '{since}'"
    query += " ORDER BY timestamp DESC LIMIT 500"
    
    try:
        results = [dict(row) for row in bq.client.query(query).result()]
        log_security_action(request, "GET_EVENTS", "SUCCESS")
        return results
    except Exception as e:
        log_security_action(request, "GET_EVENTS", f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@security_router.get("/ledger", dependencies=[Depends(verify_security_access)])
async def get_ledger(request: Request):
    """Full financial ledger snapshot."""
    bq = BigQueryClient()
    query = "SELECT * FROM `autohaus-infrastructure.autohaus_cil.financial_ledger` ORDER BY transaction_date DESC LIMIT 1000"
    
    try:
        results = [dict(row) for row in bq.client.query(query).result()]
        log_security_action(request, "GET_LEDGER", "SUCCESS")
        return results
    except Exception as e:
        log_security_action(request, "GET_LEDGER", f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@security_router.get("/entities", dependencies=[Depends(verify_security_access)])
async def get_entities(request: Request):
    """Complete entity registry view."""
    bq = BigQueryClient()
    # Summarized view of entity_facts
    query = """
        SELECT entity_id, entity_type, field_name, value, confidence_score, status
        FROM `autohaus-infrastructure.autohaus_cil.entity_facts`
        WHERE status = 'ACTIVE'
        LIMIT 2000
    """
    
    try:
        results = [dict(row) for row in bq.client.query(query).result()]
        log_security_action(request, "GET_ENTITIES", "SUCCESS")
        return results
    except Exception as e:
        log_security_action(request, "GET_ENTITIES", f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@security_router.get("/audit", dependencies=[Depends(verify_security_access)])
async def get_audit_trail(request: Request):
    """System audit log (security access logs)."""
    bq = BigQueryClient()
    query = "SELECT * FROM `autohaus-infrastructure.autohaus_cil.security_access_log` ORDER BY timestamp DESC LIMIT 1000"
    
    try:
        results = [dict(row) for row in bq.client.query(query).result()]
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ───────────────────────────────────────────────────────────────────────────────
# Control Endpoints
# ───────────────────────────────────────────────────────────────────────────────

@security_router.post("/freeze", dependencies=[Depends(verify_security_access)])
async def system_freeze(request: Request):
    """Halts all automated write operations."""
    bq = BigQueryClient()
    now_str = datetime.utcnow().isoformat()
    
    row = {
        "domain": "SYSTEM",
        "key": "FROZEN",
        "value": "true",
        "active": True,
        "version": int(datetime.utcnow().timestamp()),
        "created_at": now_str
    }
    
    try:
        bq.client.insert_rows_json("autohaus-infrastructure.autohaus_cil.policy_registry", [row])
        # Force clear policy cache
        from database.policy_engine import _engine
        _engine.clear_cache()
        
        log_security_action(request, "SYSTEM_FREEZE", "SUCCESS")
        return {"status": "FROZEN", "timestamp": now_str}
    except Exception as e:
        log_security_action(request, "SYSTEM_FREEZE", f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@security_router.post("/unfreeze", dependencies=[Depends(verify_security_access)])
async def system_unfreeze(request: Request):
    """Resumes normal operations."""
    bq = BigQueryClient()
    now_str = datetime.utcnow().isoformat()
    
    row = {
        "domain": "SYSTEM",
        "key": "FROZEN",
        "value": "false",
        "active": True,
        "version": int(datetime.utcnow().timestamp()),
        "created_at": now_str
    }
    
    try:
        bq.client.insert_rows_json("autohaus-infrastructure.autohaus_cil.policy_registry", [row])
        # Force clear policy cache
        from database.policy_engine import _engine
        _engine.clear_cache()
        
        log_security_action(request, "SYSTEM_UNFREEZE", "SUCCESS")
        return {"status": "NORMAL", "timestamp": now_str}
    except Exception as e:
        log_security_action(request, "SYSTEM_UNFREEZE", f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@security_router.post("/sync", dependencies=[Depends(verify_security_access)])
async def force_sync(request: Request):
    """Triggers an authorized git pull from origin main."""
    import subprocess
    try:
        logger.info("[SECURITY] Authorized Force Sync initiated.")
        # Execute the pull from root of repo
        # We assume the app is running in backend/ or root
        # Check for .git directory nearby
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            capture_output=True,
            text=True,
            check=True
        )
        log_security_action(request, "FORCE_SYNC", f"SUCCESS: {result.stdout}")
        return {
            "status": "SYNCED", 
            "message": "System successfully pulled latest code from main branch.",
            "git_output": result.stdout
        }
    except subprocess.CalledProcessError as e:
        log_security_action(request, "FORCE_SYNC", f"FAILED: {e.stderr}")
        return JSONResponse(
            status_code=500,
            content={"status": "ERROR", "message": "Git pull failed", "error": e.stderr}
        )
    except Exception as e:
        log_security_action(request, "FORCE_SYNC", f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))
