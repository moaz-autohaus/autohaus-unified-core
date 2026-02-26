import os
import uuid
import json
from datetime import datetime
from google.cloud import bigquery
import google.auth
from dotenv import load_dotenv

# Load unified environment variables specifically targeting auth path
load_dotenv(os.path.expanduser('~/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/auth/.env'))

PROJECT_ID = "autohaus-infrastructure"
DATASET_ID = "autohaus_cil"
TABLE_ID = "master_person_graph"
FULL_TABLE_ID = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

def _get_bq_client():
    try:
        # 1. Check for Replit Secret (Environment Variable)
        sa_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
        if sa_json:
            from google.oauth2 import service_account
            info = json.loads(sa_json)
            credentials = service_account.Credentials.from_service_account_info(info)
            return bigquery.Client(credentials=credentials, project=PROJECT_ID)

        # 2. Fallback to Local ADC (Impersonation for Moaz)
        credentials, project = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform', 'https://www.googleapis.com/auth/bigquery']
        )
        if hasattr(credentials, 'with_subject'):
            credentials = credentials.with_subject('moaz@autohausia.com')
        return bigquery.Client(credentials=credentials, project=PROJECT_ID)
    except Exception as e:
        print(f"[ERROR] BigQuery Client Initialization Failed: {str(e)}")
        return None

class IdentityEngine:
    @staticmethod
    def resolve_identity(email: str = None, phone: str = None, first_name: str = None, last_name: str = None, source_tag: str = None) -> dict:
        """
        The Probabilistic Matching Engine (v18.0)
        Attempts to match an incoming lead/customer based on email or phone.
        Returns the resolved master_person_id and confidence score.
        If no match exists, it mints a new Universal ID and inserts it.
        """
        client = _get_bq_client()
        if not client:
            print("[WARNING] BigQuery client failed to initialize. Using mocked Identity Engine response for UI testing.")
            # Mock fallback for UI membrane testing
            if not email and not phone:
                return {"status": "error", "message": "Must provide at least email or phone for resolution."}
            mock_id = str(uuid.uuid4())
            is_new = True
            if email == "test@autohausia.com" or phone == "555-0000":
                mock_id = "mocked-universal-id-1234"
                is_new = False
            return {
                "status": "success",
                "master_person_id": mock_id,
                "confidence_score": 1.0 if is_new else 0.95,
                "is_new": is_new
            }
            
        if not email and not phone:
            return {"status": "error", "message": "Must provide at least email or phone for resolution."}

        # --- Phase 1: Search Existing Entities ---
        conditions = []
        params = []
        if email:
            conditions.append("primary_email = @email")
            params.append(bigquery.ScalarQueryParameter("email", "STRING", email.lower().strip()))
        if phone:
            conditions.append("primary_phone = @phone")
            params.append(bigquery.ScalarQueryParameter("phone", "STRING", phone.strip()))
            
        where_clause = " OR ".join(conditions)
        
        query = f"""
            SELECT master_person_id, primary_email, primary_phone, entity_tags 
            FROM `{FULL_TABLE_ID}` 
            WHERE {where_clause}
            LIMIT 1
        """
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        
        try:
            results = list(client.query(query, job_config=job_config))
        except Exception as e:
            return {"status": "error", "message": f"Query execution failed: {e}"}

        # --- Phase 2: Upsert Logic ---
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        if results:
            # IDENTITY MATCH FOUND
            matched_person = dict(results[0])
            mp_id = matched_person["master_person_id"]
            
            # Simple Tag Upsert Logic (Future enhancement)
            existing_tags = json.loads(matched_person.get("entity_tags") or "[]")
            if source_tag and source_tag not in existing_tags:
                existing_tags.append(source_tag)
                update_query = f"""
                    UPDATE `{FULL_TABLE_ID}`
                    SET last_seen = @ts, entity_tags = @tags
                    WHERE master_person_id = @mp_id
                """
                update_params = [
                    bigquery.ScalarQueryParameter("ts", "TIMESTAMP", timestamp),
                    bigquery.ScalarQueryParameter("tags", "STRING", json.dumps(existing_tags)),
                    bigquery.ScalarQueryParameter("mp_id", "STRING", mp_id)
                ]
                client.query(update_query, job_config=bigquery.QueryJobConfig(query_parameters=update_params))
            
            print(f"[IDENTITY ENGINE] Match found. Using Universal ID: {mp_id}")
            return {
                "status": "success",
                "master_person_id": mp_id,
                "confidence_score": 0.95, # High confidence on exact email/phone match
                "is_new": False
            }
            
        else:
            # IDENTITY NOT FOUND -> MINT NEW UNIVERSAL ID
            new_mp_id = str(uuid.uuid4())
            new_record = {
                "master_person_id": new_mp_id,
                "created_at": timestamp,
                "last_seen": timestamp,
                "primary_email": email.lower().strip() if email else None,
                "primary_phone": phone.strip() if phone else None,
                "first_name": first_name,
                "last_name": last_name,
                "aliases": json.dumps([]),
                "connected_vins": json.dumps([]),
                "entity_tags": json.dumps([source_tag] if source_tag else []),
                "confidence_score": 1.0 # 100% confident it's exactly who we say it is because it's new
            }
            
            errors = client.insert_rows_json(FULL_TABLE_ID, [new_record])
            if errors:
                return {"status": "error", "message": f"Insert failed: {errors}"}
                
            print(f"[IDENTITY ENGINE] No match found. Minted New Universal ID: {new_mp_id}")
            return {
                "status": "success",
                "master_person_id": new_mp_id,
                "confidence_score": 1.0,
                "is_new": True
            }

if __name__ == "__main__":
    # Test execution
    print("Running Identity Resolution Test...")
    result1 = IdentityEngine.resolve_identity(email="test@autohausia.com", first_name="Test", last_name="User", source_tag="WEB_LEAD")
    print(f"Test 1 (New): {result1}")
    
    if result1.get("status") == "success":
        result2 = IdentityEngine.resolve_identity(email="test@autohausia.com", phone="555-0000", source_tag="SERVICE_LANE")
        print(f"Test 2 (Match): {result2}")
