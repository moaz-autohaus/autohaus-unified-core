from pydantic import BaseModel
from enum import Enum
from uuid import UUID
from datetime import date
from typing import Optional, List

class PolicyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PROPOSAL_PENDING_BINDING = "PROPOSAL_PENDING_BINDING"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"

class InsurancePolicy(BaseModel):
    policy_id: UUID
    policy_number: str
    carrier: str
    coverage_type: str
    covered_entity: str
    covered_location: Optional[str] = None
    effective_date: date
    expiration_date: date
    liability_limits: str
    deductible: Optional[str] = None
    policy_status: PolicyStatus
    
    # Unified policy fields:
    primary_named_insured: Optional[str] = None
    additional_insured_entities: Optional[List[str]] = None
    
    # Verification:
    authority: str = "EXTRACTED"
    verification_status: str = "PENDING_VERIFICATION"
    source_document: Optional[str] = None
    notes: Optional[str] = None
