from typing import Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from backend.app.models.enums import CampaignStatus

class CampaignBase(BaseModel):
    name: str
    description: str
    target_condition: str = "ALL"
    followup_window_hours: int = 48
    calling_hours_start: int = 9
    calling_hours_end: int = 18
    max_retries: int = 3
    priority_level: int = 3
    allocated_capacity: int = 5
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class CampaignCreate(CampaignBase):
    hospital_id: str

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_condition: Optional[str] = None
    followup_window_hours: Optional[int] = None
    calling_hours_start: Optional[int] = None
    calling_hours_end: Optional[int] = None
    max_retries: Optional[int] = None
    priority_level: Optional[int] = None
    allocated_capacity: Optional[int] = None
    status: Optional[CampaignStatus] = None

class CampaignResponse(CampaignBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    hospital_id: str
    status: CampaignStatus
    created_at: datetime
    updated_at: datetime
    total_tasks: int = 0
    completed_tasks: int = 0
    escalated_tasks: int = 0

class WorkloadEstimate(BaseModel):
    campaign_id: str
    eligible_patients_count: int
    estimated_outreach_calls: int
    estimated_completion_hours: float
    capacity_limit: int
