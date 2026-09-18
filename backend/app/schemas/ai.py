from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from backend.app.models.enums import UrgencyLevel

class ObservedIndicator(BaseModel):
    symptom_key: str
    presence: bool
    description: str
    patient_quote: Optional[str] = None
    severity: str = "NORMAL" # NORMAL, MILD, MODERATE, SEVERE, CRITICAL

class StructuredTriageOutput(BaseModel):
    triage_classification: UrgencyLevel
    confidence: float = Field(ge=0.0, le=1.0)
    observed_indicators: List[ObservedIndicator] = []
    protocol_references: List[str] = []
    clinical_reasoning: str
    escalation_recommended: bool
    suggested_nurse_actions: List[str] = []

class EvaluatorVote(BaseModel):
    evaluator_name: str # e.g. "Clinical_Acuity_Agent", "Protocol_Adherence_Agent"
    vote: UrgencyLevel
    confidence: float
    reasoning: str
    flags: List[str] = []

class EscalationConsensusResult(BaseModel):
    consensus_decision: UrgencyLevel
    escalate_to_human: bool
    agreement: bool
    disagreement_detected: bool
    disagreement_notes: Optional[str] = None
    rule_override_applied: bool = False
    votes: List[EvaluatorVote] = []
    final_rationale: str
    cited_red_flags: List[str] = []

class DocumentationOutput(BaseModel):
    summary: str
    chief_complaint: Optional[str] = None
    subjective_findings: str
    objective_data: str
    assessment: str
    plan_and_followup: str
    patient_satisfaction_note: Optional[str] = None
    requires_callback: bool = False
    callback_time: Optional[str] = None

class ControlledToolRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    caller_agent: str

class ControlledToolResponse(BaseModel):
    tool_name: str
    success: bool
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    audit_id: Optional[str] = None
