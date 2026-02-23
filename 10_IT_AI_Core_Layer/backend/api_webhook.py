import os
import json
import uuid
import datetime
from fastapi import FastAPI, HTTPException, Request
from google.cloud import bigquery
import google.auth

app = FastAPI(title="AutoHaus CIL Webhook", version="1.0")

PROJECT_ID = "autohaus-infrastructure"
DATASET_ID = "autohaus_cil"
AUDIT_TABLE = "audit_log"

@app.post("/webhook/intake")
async def handle_intake(request: Request):
    payload = await request.json()
    run_id = f"HOOK_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
    
    try:
        credentials, project = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
            
        bq_client = bigquery.Client(credentials=credentials, project=PROJECT_ID)
        
        event_type = payload.get("event", "INCOMING_PAYLOAD")
        operator_id = payload.get("operator_id", "cloud-run-webhook")
        
        # Handle State Mutations
        if event_type == "PUBLISH_TOGGLE":
            vin = payload.get("vin")
            is_published = payload.get("is_published", False)
            new_status = 'LIVE' if is_published else 'DRAFT'
            
            update_query = f"""
                UPDATE `{PROJECT_ID}.{DATASET_ID}.dim_vehicles`
                SET current_status = @status
                WHERE vin = @vin
            """
            update_job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("status", "STRING", new_status),
                    bigquery.ScalarQueryParameter("vin", "STRING", vin),
                ]
            )
            bq_client.query(update_query, job_config=update_job_config).result()
            
        elif event_type == "PROMOTE_TO_LIVE":
            vin = payload.get("vin")
            
            update_query = f"""
                UPDATE `{PROJECT_ID}.{DATASET_ID}.dim_vehicles`
                SET is_governed = TRUE, current_status = 'LIVE'
                WHERE vin = @vin
            """
            update_job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("vin", "STRING", vin),
                ]
            )
            bq_client.query(update_query, job_config=update_job_config).result()
            
        # Audit Logging (Always happens)
        query = f"""
            INSERT INTO `{PROJECT_ID}.{DATASET_ID}.{AUDIT_TABLE}` 
            (timestamp, event, operator_id, run_id)
            VALUES (CURRENT_TIMESTAMP(), @event, @operator, @run_id)
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("event", "STRING", event_type),
                bigquery.ScalarQueryParameter("operator", "STRING", operator_id),
                bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
            ]
        )
        
        query_job = bq_client.query(query, job_config=job_config)
        query_job.result()
        
        return {
            "status": "success",
            "message": "Payload registered in CIL SSOT.",
            "run_id": run_id,
            "gemini_active": bool(os.environ.get("GEMINI_API_KEY")),
            "marketcheck_active": bool(os.environ.get("MARKETCHECK_API_KEY"))
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CIL Webhook Error: {str(e)}")

@app.get("/health")
def health():
    return {"status": "alive"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("api_webhook:app", host="0.0.0.0", port=port)
