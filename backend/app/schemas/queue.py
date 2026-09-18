from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from backend.app.models.enums import TaskStatus
from backend.app.schemas.patient import PatientResponse

class OutreachTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    hospital_id: str
    campaign_id: str
    patient_id: str
    encounter_id: Optional[str] = None
    status: TaskStatus
    priority_score: float
    clinical_risk_score: float
    clinical_cutoff_time: datetime
    scheduled_for: Optional[datetime] = None
    attempts_count: int
    max_retries: int
    last_attempt_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    callback_requested_time: Optional[datetime] = None
    last_failure_reason: Optional[str] = None
    assigned_worker_id: Optional[str] = None
    call_started_at: Optional[datetime] = None
    created_at: datetime
    patient: Optional[PatientResponse] = None

class ConcurrencyStatus(BaseModel):
    hospital_id: str
    max_concurrent_capacity: int
    active_calls_count: int
    available_slots: int
    utilization_percentage: float
    pending_tasks_count: int
    oldest_pending_task_age_minutes: Optional[float] = None
    cutoff_risk_count: int # patients whose clinical cutoff is within 4 hours

class QueueSimulationStepResult(BaseModel):
    step: int
    timestamp: str
    active_calls: int
    max_capacity: int
    event: str
    task_id: str
    patient_name: str
    previous_status: str
    new_status: str
    priority_score: float
    reason: str
