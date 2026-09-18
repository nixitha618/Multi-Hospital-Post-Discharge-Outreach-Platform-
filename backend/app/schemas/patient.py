from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from backend.app.models.enums import RiskTier

class ConditionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    icd10_code: str
    name: str
    clinical_status: str

class MedicationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    dosage: str
    instructions: str
    active: bool

class CarePlanSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    protocol_code: str
    target_window_hours: int
    instructions: str
    red_flag_warnings: str

class EncounterSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    encounter_type: str
    admission_date: datetime
    discharge_date: datetime
    discharge_disposition: str
    attending_physician: str
    primary_diagnosis: str
    discharge_summary: str

class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    hospital_id: str
    mrn: str
    first_name: str
    last_name: str
    date_of_birth: str
    gender: str
    phone_number: str
    email: Optional[str] = None
    preferred_language: str
    consent_for_outreach: bool
    preferred_call_window_start: int
    preferred_call_window_end: int
    baseline_risk_score: float
    risk_tier: RiskTier
    created_at: datetime

class PatientDetailResponse(PatientResponse):
    encounters: List[EncounterSchema] = []
    conditions: List[ConditionSchema] = []
    medications: List[MedicationSchema] = []
    care_plans: List[CarePlanSchema] = []
