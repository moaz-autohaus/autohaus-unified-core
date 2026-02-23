from google.cloud import bigquery
import google.auth
import sys

# AutoHaus Unified Infrastructure: SSOT View Provisioning (v3.1)
# Defines the `vw_website_inventory` view for the Stateless Web Interface.

PROJECT_ID = "autohaus-infrastructure"
DATASET_ID = "autohaus_cil"
VIEW_ID = f"{PROJECT_ID}.{DATASET_ID}.vw_website_inventory"

def provision_ssot_view():
    print(f"[PROVISION] Defining SSOT View: {VIEW_ID} ...")
    
    try:
        credentials, project = google.auth.default()
        client = bigquery.Client(credentials=credentials, project=PROJECT_ID)
        
        # 1. Define the View Logic
        # It must JOIN the master_inventory with the governance_registry
        # Filter: Show only vehicles where status = 'LIVE'
        # Output: A JSON-ready schema for the Replit GET /api/vehicles endpoint.
        
        view_query = f"""
            SELECT 
                i.id AS vehicle_id,
                i.make,
                i.model,
                i.year,
                i.category,
                i.price,
                i.mileage,
                i.fuelType,
                i.transmission,
                i.color,
                i.description,
                i.imageUrl,
                g.status AS governance_status,
                g.last_updated
            FROM 
                `{PROJECT_ID}.{DATASET_ID}.inventory_master` i
            JOIN 
                `{PROJECT_ID}.{DATASET_ID}.governance_registry` g
            ON 
                i.id = g.vehicle_id
            WHERE 
                g.status = 'LIVE'
                AND i.is_active = TRUE
        """
        
        # Note: Since the dataset is currently invisible via CLI/API for the active user,
        # we are capturing the logic as requested by the Architect, rather than executing it directly.
        # This acts as the SQL definition script.
        
        print("\n--- [SSOT VIEW SQL DEFINITION] ---")
        print(view_query)
        print("----------------------------------\n")
        
        print("[SUCCESS] View SQL Defined.")
        print("[NOTE] Direct creation bypassed due to pending IAM/Dataset visibility resolution.")
        
        return True

    except Exception as e:
        print(f"[CRITICAL] View Provisioning Failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = provision_ssot_view()
    if not success:
        sys.exit(1)
