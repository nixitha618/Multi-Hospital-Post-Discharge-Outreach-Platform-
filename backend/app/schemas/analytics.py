from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class CampaignReprioritizeRequest(BaseModel):
    priority_level: int # 1 to 5
    allocated_capacity: int # 1 to 10
    calling_hours_start: Optional[int] = None
    calling_hours_end: Optional[int] = None

class OutcomeBreakdown(BaseModel):
    completed: int = 0
    no_answer: int = 0
    busy: int = 0
    voicemail: int = 0
    dropped: int = 0
    escalated: int = 0
    callback_requested: int = 0
    technical_failure: int = 0

class RetryDistribution(BaseModel):
    attempt_1: int = 0
    attempt_2: int = 0
    attempt_3: int = 0
    exhausted_max: int = 0

class HospitalStaffActivityItem(BaseModel):
    timestamp: str
    actor_id: str
    actor_role: str
    action: str
    target_entity: str
    target_id: Optional[str] = None
    details: Optional[str] = None

class HospitalCampaignSummary(BaseModel):
    id: str
    name: str
    target_condition: str
    status: str
    priority_level: int
    allocated_capacity: int
    total_tasks: int
    completed_tasks: int
    escalated_tasks: int
    pending_tasks: int
    progress_percentage: float

class HospitalOperationalMetrics(BaseModel):
    hospital_id: str
    hospital_name: str
    timezone: str
    timestamp: str

    # Outreach volume & state
    total_tasks: int
    pending_tasks: int
    active_calling_tasks: int
    completed_tasks: int
    escalated_tasks: int
    manual_followup_tasks: int
    failed_tasks: int

    # Contact rates & performance
    contact_rate_pct: float
    escalation_rate_pct: float
    average_attempts: float
    queue_wait_average_mins: float
    capacity_utilization_pct: float
    active_slots: int
    max_slots: int

    # Distributions
    outcomes: OutcomeBreakdown
    retries: RetryDistribution

    # EHR & System Health
    ehr_synced_count: int
    ehr_failed_count: int
    ehr_status: str
    ehr_simulate_failure: bool

    # Active Campaigns
    campaigns: List[HospitalCampaignSummary] = []

    # Staff activity & audit
    recent_staff_activity: List[HospitalStaffActivityItem] = []

class HospitalFleetItem(BaseModel):
    hospital_id: str
    name: str
    timezone: str
    status: str
    max_concurrency_capacity: int
    active_calls: int
    capacity_utilization_pct: float
    active_campaigns_count: int
    total_tasks_count: int
    pending_tasks_count: int
    completed_tasks_count: int
    escalations_count: int
    ehr_status: str

class PlatformAIUsage(BaseModel):
    total_calls_processed: int
    total_tokens_consumed: int
    average_latency_ms: int
    estimated_cost_usd: float
    consensus_agreement_rate_pct: float
    schema_validation_failure_rate_pct: float

class PlatformOperationalMetrics(BaseModel):
    timestamp: str
    total_hospitals: int
    active_hospitals_count: int
    total_campaigns: int
    active_campaigns: int

    # Cross-Hospital Fleet Capacity
    fleet_max_capacity: int
    fleet_active_calls: int
    fleet_capacity_utilization_pct: float
    total_pending_queue: int
    total_completed_outreach: int
    total_platform_escalations: int

    # Per-hospital breakdown (Tenant-isolated aggregate metrics)
    hospitals: List[HospitalFleetItem] = []

    # Platform AI usage & costs
    ai_usage: PlatformAIUsage

    # System errors & resilience
    total_technical_failures: int
    total_ehr_sync_failures: int
    system_status: str # HEALTHY, DEGRADED
    worker_recovery_count: int

class PatientOperationalEncounter(BaseModel):
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    discharge_disposition: Optional[str] = "Home"
    attending_physician: Optional[str] = None
    primary_diagnosis: Optional[str] = None
    discharge_summary: Optional[str] = None

class PatientOperationalTask(BaseModel):
    task_id: str
    campaign_name: str
    status: str
    priority_score: float
    attempts_count: int
    max_retries: int
    clinical_cutoff_time: Optional[str] = None
    next_retry_at: Optional[str] = None
    last_failure_reason: Optional[str] = None

class PatientOperationalCall(BaseModel):
    call_id: str
    attempt_number: int
    start_time: str
    duration_seconds: int
    outcome: str
    triage_classification: Optional[str] = None
    consensus_decision: Optional[str] = None
    observations: List[str] = []
    protocol_citations: List[str] = []
    documentation_summary: Optional[str] = None
    ehr_sync_status: str
    dialogue_turns: List[Dict[str, Any]] = []

class PatientOperationalEscalation(BaseModel):
    escalation_id: str
    severity: str
    status: str
    created_at: str
    trigger_reason: str
    clinical_indicators: str
    assigned_reviewer_name: Optional[str] = None
    resolution_action: Optional[str] = None
    resolution_notes: Optional[str] = None
    resolved_at: Optional[str] = None

class PatientOperationalViewResponse(BaseModel):
    patient_id: str
    hospital_id: str
    mrn: str
    full_name: str
    date_of_birth: str
    gender: str
    phone_number: str
    preferred_language: str
    consent_for_outreach: bool
    preferred_call_window: str
    baseline_risk_score: float
    risk_tier: str

    encounter: Optional[PatientOperationalEncounter] = None
    active_task: Optional[PatientOperationalTask] = None
    calls: List[PatientOperationalCall] = []
    escalations: List[PatientOperationalEscalation] = []
    conditions: List[str] = []
    medications: List[str] = []
    care_plan_instructions: Optional[str] = None
