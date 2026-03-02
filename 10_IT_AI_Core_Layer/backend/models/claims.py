import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, ValidationError

class ClaimSource(str, Enum):
    GMAIL = "GMAIL"
    ATTACHMENT = "ATTACHMENT"
    MEDIA = "MEDIA"
    MANUAL = "MANUAL"

class EntityType(str, Enum):
    VEHICLE = "VEHICLE"
    PERSON = "PERSON"
    VENDOR = "VENDOR"
    DOCUMENT = "DOCUMENT"
    UNKNOWN = "UNKNOWN"

class ClaimStatus(str, Enum):
    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"

class ExtractedClaim(BaseModel):
    claim_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    source: ClaimSource
    extractor_identity: str
    input_reference: str
    entity_type: EntityType
    target_entity_id: Optional[str] = None
    target_field: str
    extracted_value: str
    confidence: float
    source_lineage: Dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: ClaimStatus = ClaimStatus.PENDING

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v
    
    @classmethod
    def from_gemini_response(cls, raw: dict) -> "ExtractedClaim":
        """
        Maps a raw Gemini JSON output to this schema.
        Raises a structured ValidationError if required fields are missing.
        """
        return cls(**raw)

class AssertionType(str, Enum):
    VERIFIABLE_FACT = "VERIFIABLE_FACT"
    INTENT = "INTENT"
    CONTEXT = "CONTEXT"

class VerificationStatus(str, Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    PENDING_CORROBORATION = "PENDING_CORROBORATION"
    VERIFIED = "VERIFIED"
    CORROBORATED = "CORROBORATED"
    CONTRADICTED = "CONTRADICTED"
    CONTESTED = "CONTESTED"

class HumanAssertion(BaseModel):
    assertion_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    asserted_by: str
    asserted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assertion_type: AssertionType
    content: str
    authority: str = "HUMAN_ASSERTED"

    # For VERIFIABLE_FACT only:
    evidence_required: Optional[str] = None
    verified_by_document: Optional[str] = None

    # For INTENT and CONTEXT only:
    evidence_structure: Optional[list[str]] = None
    corroboration_score: Optional[float] = 0.0
    corroboration_threshold: Optional[float] = 0.75
    supporting_documents: Optional[list[str]] = []

    # Shared across all types:
    verification_status: VerificationStatus
    downstream_dependents: list[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("evidence_required")
    @classmethod
    def validate_evidence_required(cls, v: Optional[str], info) -> Optional[str]:
        if info.data.get("assertion_type") == AssertionType.VERIFIABLE_FACT and not v:
            raise ValueError("VERIFIABLE_FACT requires evidence_required to be set")
        return v

    @field_validator("evidence_structure")
    @classmethod
    def validate_evidence_structure(cls, v: Optional[list[str]], info) -> Optional[list[str]]:
        ast_type = info.data.get("assertion_type")
        if ast_type in (AssertionType.INTENT, AssertionType.CONTEXT):
            if not v or len(v) == 0:
                raise ValueError(f"{ast_type.value} requires evidence_structure to be set with at least one entry")
        return v

    @field_validator("corroboration_score")
    @classmethod
    def validate_corroboration_score(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("corroboration_score must be between 0.0 and 1.0")
        return v

    @classmethod
    def from_human_input(
        cls,
        content: str,
        assertion_type: AssertionType,
        asserted_by: str,
        evidence_required: Optional[str] = None,
        evidence_structure: Optional[list[str]] = None
    ) -> "HumanAssertion":
        
        status = VerificationStatus.PENDING_VERIFICATION
        if assertion_type in (AssertionType.INTENT, AssertionType.CONTEXT):
            status = VerificationStatus.PENDING_CORROBORATION

        return cls(
            content=content,
            assertion_type=assertion_type,
            asserted_by=asserted_by,
            evidence_required=evidence_required,
            evidence_structure=evidence_structure,
            verification_status=status
        )

