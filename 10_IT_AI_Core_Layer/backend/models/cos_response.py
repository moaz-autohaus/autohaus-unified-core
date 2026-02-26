from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class UIStrategyModel(BaseModel):
    skin: str
    urgency: int
    vibration: bool
    overlay: Optional[str] = None

class CoSResponse(BaseModel):
    """
    Strict API Contract for the Chief of Staff AI.
    Prevents UI hydration failures and ensures predictable streaming.
    """
    type: str # ResponseType Enum-like behavior in practice
    message: Optional[str] = None
    plate_id: Optional[str] = None
    intent: Optional[str] = None
    confidence: float = 1.0
    entities: Dict[str, Any] = Field(default_factory=dict)
    target_entity: str = "SYSTEM"
    suggested_action: Optional[str] = None
    strategy: Optional[UIStrategyModel] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    dataset: List[Any] = Field(default_factory=list)
    
    # Metadata
    connected_clients: Optional[int] = None
    authority_state: Optional[str] = None
    legacy_sync: Optional[bool] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "MOUNT_PLATE",
                "plate_id": "FINANCE_CHART",
                "intent": "FINANCE",
                "confidence": 0.98,
                "target_entity": "CARBON_LLC",
                "strategy": {
                    "skin": "SUPER_ADMIN",
                    "urgency": 5,
                    "vibration": False
                }
            }
        }
