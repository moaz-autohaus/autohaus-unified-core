import os
import uuid
import json
from datetime import datetime

import google.auth
from googleapiclient.discovery import build # Added import for build

PROJECT_ID = "457080741078"

def get_bq_client():
    try:
        credentials, project = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform', 'https://www.googleapis.com/auth/bigquery']
        )
        # Impersonate Corporate Unified Identity
        if hasattr(credentials, 'with_subject'):
            credentials = credentials.with_subject('moaz@autohausia.com')
            
        print(f"ADC Auth Successful [Project: {PROJECT_ID} | Subject: moaz@autohausia.com]")
        return bigquery.Client(credentials=credentials, project=PROJECT_ID)
    except Exception as e:
        raise RuntimeError(f"ADC Authentication Failed: {str(e)}")

def push_ghost_inventory():
    """Seeds the autohaus_cil.inventory_master table with Unified Stock."""
    client = get_bq_client()
    table_id = f"{client.project}.autohaus_cil.inventory_master"
    
    # "Ghost" Master Stock
    rows_to_insert = [
        {
            "id": "GT3-992-001",
            "make": "Porsche",
            "model": "911 GT3 (992)",
            "year": 2024,
            "category": "Coupe",
            "price": "245000.00",
            "mileage": 1200,
            "fuelType": "Gasoline",
            "transmission": "PDK",
            "color": "Shark Blue",
            "description": "Mint condition track weapon. Full PPF, carbon buckets.",
            "imageUrl": "https://images.unsplash.com/photo-1503376713292-01994e412d22?q=80&w=2000",
            "status": "available",
            "is_active": True
        },
        {
            "id": "G63-AMG-002",
            "make": "Mercedes-Benz",
            "model": "G-Class AMG 63",
            "year": 2023,
            "category": "SUV",
            "price": "198000.00",
            "mileage": 8500,
            "fuelType": "Gasoline",
            "transmission": "Automatic",
            "color": "Obsidian Black",
            "description": "Ultimate luxury SUV. Night package, red calipers, pristine.",
            "imageUrl": "https://images.unsplash.com/photo-1520031441872-265e4ff70366?auto=format&fit=crop&q=80&w=2000",
            "status": "available",
            "is_active": True
        },
        {
            "id": "R8-V10-003",
            "make": "Audi",
            "model": "R8 V10 Performance",
            "year": 2022,
            "category": "Coupe",
            "price": "185000.00",
            "mileage": 14000,
            "fuelType": "Gasoline",
            "transmission": "S-tronic",
            "color": "Daytona Gray",
            "description": "Naturally aspirated V10 symphony. Carbon exterior package.",
            "imageUrl": "https://images.unsplash.com/photo-1603584173870-7f23fdae1b7a?auto=format&fit=crop&q=80&w=2000",
            "status": "available",
            "is_active": True
        },
        {
            "id": "PLAID-X-004",
            "make": "Tesla",
            "model": "Model X Plaid",
            "year": 2024,
            "category": "Electric",
            "price": "104900.00",
            "mileage": 500,
            "fuelType": "Electric",
            "transmission": "Direct Drive",
            "color": "Pearl White",
            "description": "Family hauler that outruns supercars. 6-seat interior, FSD.",
            "imageUrl": "https://images.unsplash.com/photo-1560958089-b8a1929cea89?auto=format&fit=crop&q=80&w=2000",
            "status": "available",
            "is_active": True
        },
        {
            "id": "M5-CS-005",
            "make": "BMW",
            "model": "M5 CS",
            "year": 2022,
            "category": "Sedan",
            "price": "142000.00",
            "mileage": 9600,
            "fuelType": "Gasoline",
            "transmission": "Automatic",
            "color": "Frozen Deep Green Metallic",
            "description": "The peak of the F90 generation. Carbon fiber seats, gold bronze accents.",
            "imageUrl": "https://images.unsplash.com/photo-1555215695-3004980ad54e?auto=format&fit=crop&q=80&w=2000",
            "status": "available",
            "is_active": True
        }
    ]
    
    # Fire off to the CIL Data Lake
    print(f"Seeding {len(rows_to_insert)} 'Ghost' vehicles to {table_id}...")
    
    errors = client.insert_rows_json(table_id, rows_to_insert)
    
    if not errors:
        print("[SUCCESS] Inventory Seeded! is_active flags = True. View ready to ingest.")
        
        # Emit SEEDING_TIER_COMPLETED event
        try:
            event_id = str(uuid.uuid4())
            event_row = {
                "event_id": event_id,
                "event_type": "SEEDING_TIER_COMPLETED",
                "timestamp": datetime.utcnow().isoformat(),
                "actor_type": "SYSTEM",
                "actor_id": "seeding_script",
                "actor_role": "ADMIN",
                "target_type": "SYSTEM",
                "target_id": "INVENTORY_MASTER",
                "payload": json.dumps({
                    "tier": "GHOST_INVENTORY",
                    "record_count": len(rows_to_insert),
                    "status": "SUCCESS"
                }),
                "metadata": None,
                "idempotency_key": f"seed_{event_id}"
            }
            client.insert_rows_json(f"{client.project}.autohaus_cil.cil_events", [event_row])
            print(f"[LEDGER] Seeding receipt emitted: {event_id}")
        except Exception as e:
            print(f"[WARNING] Failed to emit seeding receipt: {e}")
    else:
        print("[ERROR] Failed to push to CIL:")
        for e in errors:
            print(e)
            
if __name__ == "__main__":
    push_ghost_inventory()
