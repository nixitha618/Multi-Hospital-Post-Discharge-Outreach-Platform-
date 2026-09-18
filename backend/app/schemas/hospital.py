from typing import Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from backend.app.models.enums import HospitalStatus

class HospitalBase(BaseModel):
    name: str
    code: str
    timezone: str = "America/New_York"
    contact_email: str
    contact_phone: str
    permitted_call_start_hour: int = 9
    permitted_call_end_hour: int = 18
    max_concurrent_calls: int = 5
    max_retries: int = 3
    retry_backoff_minutes: str = "15,60,240"
    mock_ehr_endpoint: str = "mock://ehr-default"

class HospitalCreate(HospitalBase):
    id: Optional[str] = None

class HospitalUpdate(BaseModel):
    name: Optional[str] = None
    timezone: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    permitted_call_start_hour: Optional[int] = None
    permitted_call_end_hour: Optional[int] = None
    max_concurrent_calls: Optional[int] = None
    max_retries: Optional[int] = None
    retry_backoff_minutes: Optional[str] = None
    status: Optional[HospitalStatus] = None

class HospitalResponse(HospitalBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: HospitalStatus
    created_at: datetime
    updated_at: datetime
