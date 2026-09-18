from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from backend.app.models.enums import EscalationStatus, UrgencyLevel
from backend.app.schemas.patient import PatientResponse

class EscalationNoteCreate(BaseModel):
    note_text: str
    author_name: Optional[str] = "Nurse Reviewer"

class EscalationNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    escalation_id: str
    author_id: str
    author_name: str
    note_text: str
    created_at: datetime

class EscalationResolveRequest(BaseModel):
    resolution_notes: str
    resolution_action: str # e.g., "Urgent clinic appointment scheduled for tomorrow 9 AM"
    reviewer_name: str

class EscalationAssignRequest(BaseModel):
    reviewer_id: str
    reviewer_name: str

class EscalationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    hospital_id: str
    task_id: str
    call_id: Optional[str] = None
    patient_id: str
    campaign_id: str
    status: EscalationStatus
    severity: UrgencyLevel
    trigger_reason: str
    clinical_indicators: str
    protocol_citations: str
    consensus_rationale: str
    assigned_reviewer_id: Optional[str] = None
    assigned_reviewer_name: Optional[str] = None
    resolution_notes: Optional[str] = None
    resolution_action: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by_user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    notes: List[EscalationNoteResponse] = []
    patient: Optional[PatientResponse] = None
    attempts_count: Optional[int] = 1
    max_retries: Optional[int] = 3
