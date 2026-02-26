
from fastapi import APIRouter, HTTPException, Depends
from google.cloud import bigquery
from google.oauth2 import service_account
import os

anomalies_router = APIRouter()

PROJECT_ID = "autohaus-infrastructure"
KEY_PATH = "/Users/moazsial/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/backend/auth/replit-sa-key.json"

def get_bq_client():
    if os.path.exists(KEY_PATH):
        credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
        return bigquery.Client(credentials=credentials, project=PROJECT_ID)
    return None

@anomalies_router.get("/active")
async def get_active_anomalies(client: bigquery.Client = Depends(get_bq_client)):
    # Standard response shape
    data = {
        "anomalies": []
    }
    
    if not client:
        return data
        
    try:
        # Fetch from BigQuery if tables have data
        query = "SELECT * FROM `autohaus_cil.drift_sweep_results` WHERE resolved = FALSE LIMIT 50"
        query_job = client.query(query)
        results = []
        for row in query_job:
            results.append({
                "id": row.sweep_id,
                "type": row.sweep_type,
                "severity": row.severity,
                "entity_id": row.target_id,
                "description": row.finding,
                "detected_at": row.created_at.isoformat() if row.created_at else None
            })
        data["anomalies"] = results
        return data
    except Exception as e:
        print(f"Anomalies fetch error: {e}")
        return data
