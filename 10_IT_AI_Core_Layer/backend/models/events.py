from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

class ActorType(str, Enum):
    SYSTEM = "SYSTEM"
    HUMAN = "HUMAN"
    HITL_SERVICE = "HITL_SERVICE"

class ActorRole(str, Enum):
    SOVEREIGN = "SOVEREIGN"
    STANDARD = "STANDARD"
    FIELD = "FIELD"
    SYSTEM = "SYSTEM"

class TargetType(str, Enum):
    DOCUMENT = "DOCUMENT"
    ENTITY = "ENTITY"
    TRANSACTION = "TRANSACTION"
    PLATE = "PLATE"
    QUESTION = "QUESTION"

class EventType(str, Enum):
    DOCUMENT_REGISTERED = "DOCUMENT_REGISTERED"
    OCR_COMPLETED = "OCR_COMPLETED"
    FIELD_EXTRACTED = "FIELD_EXTRACTED"
    HITL_FIELD_OVERRIDE_APPLIED = "HITL_FIELD_OVERRIDE_APPLIED"
    ENTITY_LINKED = "ENTITY_LINKED"
    UI_RENDER_FAILED = "UI_RENDER_FAILED"
    INGESTION_RUN_COMPLETED = "INGESTION_RUN_COMPLETED"
    SEEDING_TIER_COMPLETED = "SEEDING_TIER_COMPLETED"
    ENTITY_ENRICHED = "ENTITY_ENRICHED"
    ENTITY_CREATED = "ENTITY_CREATED"
    # Other events can be added here as needed

# Event Payload Models
class PayloadDocumentRegistered(BaseModel):
    drive_id: str
    content_hash: str
    mime: str

class PayloadOcrCompleted(BaseModel):
    page_count: int
    confidence_avg: float
    ocr_gcs_uri: str

class ExtractedField(BaseModel):
    value: Any
    confidence: float

class PayloadFieldExtracted(BaseModel):
    schema_id: str
    fields: Dict[str, ExtractedField]

class PayloadHitlFieldOverrideApplied(BaseModel):
    field_name: str
    old_value: Optional[str] = None
    new_value: str
    hitl_event_id: str

class PayloadEntityLinked(BaseModel):
    entity_type: str
    entity_id: str
    confidence: float
    method: str  # EXACT_MATCH, IDENTITY_ENGINE, etc.

class PayloadEntityCreated(BaseModel):
    entity_type: str
    entity_id: str
    status: str
    authority_level: str
    anchors: Optional[Dict[str, Any]] = None
    lineage: Optional[List[str]] = None

class PayloadEntityEnriched(BaseModel):
    entity_type: str
    entity_id: str
    method: str

class EventMetadata(BaseModel):
    latency_ms: Optional[int] = None
    api_model: Optional[str] = None
    cost_usd: Optional[float] = None
    reason: Optional[str] = None

class CILEvent(BaseModel):
    event_id: str
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actor_type: ActorType
    actor_id: Optional[str] = None
    actor_role: Optional[ActorRole] = None
    target_type: TargetType
    target_id: str
    payload: Dict[str, Any]  # To be validated based on event_type if necessary
    metadata: Optional[EventMetadata] = None
    idempotency_key: Optional[str] = None
    
    # Custom validation can be added here to strictly check `payload` against `event_type`.
    
    @classmethod
    def validate_payload(cls, event_type: EventType, payload: Dict[str, Any]):
        if event_type == EventType.DOCUMENT_REGISTERED:
            return PayloadDocumentRegistered(**payload)
        elif event_type == EventType.OCR_COMPLETED:
            return PayloadOcrCompleted(**payload)
        elif event_type == EventType.FIELD_EXTRACTED:
            return PayloadFieldExtracted(**payload)
        elif event_type == EventType.HITL_FIELD_OVERRIDE_APPLIED:
            return PayloadHitlFieldOverrideApplied(**payload)
        elif event_type == EventType.ENTITY_LINKED:
            return PayloadEntityLinked(**payload)
        elif event_type == EventType.ENTITY_CREATED:
            return PayloadEntityCreated(**payload)
        # Default fallback
        return payload
