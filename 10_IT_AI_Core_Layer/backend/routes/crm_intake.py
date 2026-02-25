from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from utils.identity_resolution import IdentityEngine

crm_router = APIRouter()

class LeadIntakeRequest(BaseModel):
    source: str
    email: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

@crm_router.post("/intake")
async def process_crm_intake(payload: LeadIntakeRequest):
    """
    Module 1: Identity Bedrock CRM Intake Endpoint
    Processes inbound leads and merges/resolves them against the Human Graph (BigQuery).
    Returns the Universal Master Person ID and confidence score.
    """
    if not payload.email and not payload.phone:
        raise HTTPException(
            status_code=400, 
            detail="Must provide at least email or phone for probabilistic identity resolution."
        )
        
    try:
        result = IdentityEngine.resolve_identity(
            email=payload.email,
            phone=payload.phone,
            first_name=payload.first_name,
            last_name=payload.last_name,
            source_tag=payload.source
        )
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
            
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal CRM Intake Error: {str(e)}")
