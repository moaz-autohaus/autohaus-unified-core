import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from google.cloud import bigquery

from database.bigquery_client import get_database

logger = logging.getLogger("autohaus.public_api")
public_router = APIRouter()

class LeadRequest(BaseModel):
    name: str
    phone: str
    email: str
    interest_vin: str = None
    message: str = None
    source: str = "WEBSITE"

class AppointmentRequest(BaseModel):
    name: str
    phone: str
    service_type: str
    preferred_date: str
    preferred_time: str
    vehicle_vin: str = None

@public_router.get("/inventory")
async def get_public_inventory(client: bigquery.Client = Depends(get_database)):
    """
    Returns only vehicles with status 'AVAILABLE'.
    Strips all pricing except listing_price and removes sensitive internal flags.
    """
    query = """
        SELECT 
            v.vin,
            v.year,
            v.make,
            v.model,
            v.trim,
            v.color,
            MAX(CASE WHEN f.field_name = 'listing_price' THEN CAST(f.value AS FLOAT64) END) as listing_price,
            MAX(CASE WHEN f.field_name = 'mileage' THEN CAST(f.value AS INT64) END) as mileage,
            MAX(CASE WHEN f.field_name = 'nhtsa_overall_rating' THEN f.value END) as safety_rating
        FROM `autohaus-infrastructure.autohaus_cil.vehicles` v
        LEFT JOIN `autohaus-infrastructure.autohaus_cil.entity_facts` f ON v.vehicle_id = f.entity_id
        WHERE v.status = 'AVAILABLE' AND f.status = 'ACTIVE'
        GROUP BY v.vin, v.year, v.make, v.model, v.trim, v.color
    """
    try:
        rows = list(client.query(query).result())
        return {"vehicles": [dict(r) for r in rows], "count": len(rows)}
    except Exception as e:
        logger.error(f"Public API error: {e}")
        raise HTTPException(status_code=500, detail="Database lookup failed")

@public_router.post("/lead")
async def process_incoming_lead(lead: LeadRequest, bg_tasks: BackgroundTasks, client: bigquery.Client = Depends(get_database)):
    """
    Intakes a web lead, routes to CRM, triggers entity creation, and fires a notification.
    """
    logger.info(f"[PUBLIC API] Received lead from {lead.name} for VIN {lead.interest_vin}")
    
    def process_lead_async():
        # This will resolve person, create Person entity, enrich person
        from pipeline.entity_resolution import resolve_person
        person_id, method, data = resolve_person(client, name=lead.name, phone=lead.phone, email=lead.email)
        
        # Then notify the CEO / Sales Team via Router
        import asyncio
        from integrations.notification_router import NotificationRouter
        router = NotificationRouter(client)
        asyncio.run(router.notify_role(
            role="CEO", 
            template="new_lead_alert", 
            data={"customer_name": lead.name, "vin": lead.interest_vin, "phone": lead.phone},
            urgency="HIGH"
        ))

    bg_tasks.add_task(process_lead_async)
    
    return {"status": "received", "message": "Thank you! We'll be in touch shortly."}

@public_router.post("/appointment")
async def process_appointment_request(app: AppointmentRequest):
    """
    Proposes an appointment in the Calendar Spoke. Sandbox-first.
    """
    logger.info(f"[PUBLIC API] Received appointment request from {app.name}")
    # Integration logic with CalendarSpoke would go here asynchronously
    return {"status": "requested", "message": f"Appointment requested for {app.preferred_date}. We'll confirm shortly."}
