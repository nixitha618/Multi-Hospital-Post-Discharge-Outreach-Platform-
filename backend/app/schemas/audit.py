from typing import Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class AuditLogCreate(BaseModel):
    hospital_id: Optional[str] = None
    actor_id: str
    actor_role: str
    action: str
    target_entity: str
    target_id: str
    details_json: Optional[str] = None
    client_ip: Optional[str] = None

class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    hospital_id: Optional[str] = None
    timestamp: datetime
    actor_id: str
    actor_role: str
    action: str
    target_entity: str
    target_id: str
    details_json: Optional[str] = None
    client_ip: Optional[str] = None
