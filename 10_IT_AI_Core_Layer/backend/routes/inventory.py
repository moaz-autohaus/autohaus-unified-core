from fastapi import APIRouter, HTTPException, Depends, Query
from google.cloud import bigquery
from google.oauth2 import service_account
import os
from utils.audit_watcher import AuditWatcher, GovernanceException

inventory_router = APIRouter()

import google.auth

inventory_router = APIRouter()
PROJECT_ID = "457080741078"

# --- Security Dependency (ADC with Impersonation) ---
def get_bq_client():
    try:
        credentials, project = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform', 'https://www.googleapis.com/auth/bigquery']
        )
        # Impersonate Corporate Unified Identity
        if hasattr(credentials, 'with_subject'):
            credentials = credentials.with_subject('moaz@autohausia.com')
        
        return bigquery.Client(credentials=credentials, project=PROJECT_ID)
    except Exception as e:
        print(f"ERROR: ADC Impersonation Failed: {str(e)}")
        return None


# --- Unified Logic: Identity Fork (Registry-Based) ---
def get_labor_rate(entity_id: str):
    """
    Tier 2: Rate-Maker.
    KAMM LLC (Internal): $95/hr | Retail: $135/hr
    Stored in backend/registry/personnel.json
    """
    registry_path = os.path.join(os.path.dirname(__file__), "..", "registry", "personnel.json")
    try:
        with open(registry_path, "r") as f:
            personnel = json.load(f)
            # Find a matching role/rate (Standardizing on internal/retail)
            # For now, mapping entity_id to the key in the first personnel entry
            rates = personnel[0]["billing_rates"]
            return rates.get("internal" if entity_id == "KAMM_LLC" else "retail", 135)
    except Exception:
        return 135 # Fallback to Retail

# --- Universal Data Bridge ---
@inventory_router.get("/")
async def get_inventory(
    public: bool = False, 
    audit_context: dict = None,
    client: bigquery.Client = Depends(get_bq_client)
):
    # Enforce Audit Traceability
    try:
        AuditWatcher.verify_context(audit_context)
    except GovernanceException as e:
        # In public mode, we might allow read-only without full context for now
        # but internal/filtered queries MUST be traceable.
        if not public:
            raise HTTPException(status_code=403, detail=str(e))

    if not client:
        raise HTTPException(status_code=500, detail="BigQuery Link Offline.")
        
    # Governance Oversight: External access must be explicitly public
    if not public:
        raise HTTPException(
            status_code=403, 
            detail="Governance Breach: Public visibility must be explicitly requested via ?public=true"
        )
        
    query = "SELECT * FROM `autohaus_cil.vw_live_inventory`"
    try:
        query_job = client.query(query)
        # BQ Output -> Dictionary list
        return [dict(row) for row in query_job]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CIL Core Fetch Error: {str(e)}")


@inventory_router.get("/{vehicle_id}")
async def get_vehicle(
    vehicle_id: str, 
    public: bool = False,
    client: bigquery.Client = Depends(get_bq_client)
):
    if not client:
        raise HTTPException(status_code=500, detail="BigQuery Link Offline.")

    if not public:
        raise HTTPException(
            status_code=403, 
            detail="Governance Breach: Direct CIL Vault access requires ?public=true oversight."
        )
        
    query = "SELECT * FROM `autohaus_cil.vw_live_inventory` WHERE id = @v_id LIMIT 1"
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("v_id", "STRING", vehicle_id)]
    )
    try:
        query_job = client.query(query, job_config=job_config)
        results = [dict(row) for row in query_job]
        if not results:
            raise HTTPException(status_code=404, detail="Vehicle not found in global CIL.")
        return results[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CIL Core Fetch Error: {str(e)}")
