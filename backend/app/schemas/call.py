from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from backend.app.models.enums import CallOutcome, UrgencyLevel

class CallTurnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    speaker: str
    text: str
    turn_index: int
    intent: Optional[str] = None
    created_at: datetime

class CallRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    hospital_id: str
    task_id: str
    patient_id: str
    campaign_id: str
    attempt_number: int
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: int
    outcome: CallOutcome
    raw_transcript: Optional[str] = None
    triage_classification: Optional[UrgencyLevel] = None
    clinical_observations_json: Optional[str] = None
    protocol_citations_json: Optional[str] = None
    consensus_decision: Optional[str] = None
    consensus_disagreement: bool = False
    consensus_details_json: Optional[str] = None
    escalation_created: bool = False
    documentation_summary: Optional[str] = None
    ehr_sync_status: str
    ehr_sync_details: Optional[str] = None
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    estimated_cost: float
    latency_ms: int
    created_at: datetime
    turns: List[CallTurnResponse] = []

class CallInitiateRequest(BaseModel):
    task_id: str
    worker_id: Optional[str] = "worker-sim-01"

class InteractiveTurnRequest(BaseModel):
    call_id: str
    patient_speech: str
