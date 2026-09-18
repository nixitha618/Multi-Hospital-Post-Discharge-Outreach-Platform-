from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class FHIRCoding(BaseModel):
    system: str
    code: str
    display: str

class FHIRCodeableConcept(BaseModel):
    coding: List[FHIRCoding]
    text: Optional[str] = None

class FHIRObservation(BaseModel):
    resourceType: str = "Observation"
    id: Optional[str] = None
    status: str = "final" # final, amended
    code: FHIRCodeableConcept
    subject_reference: str # e.g. "Patient/pat-101"
    encounter_reference: Optional[str] = None
    effectiveDateTime: datetime = Field(default_factory=datetime.utcnow)
    valueString: Optional[str] = None
    valueQuantity: Optional[Dict[str, Any]] = None
    interpretation: Optional[str] = None # NORMAL, ABNORMAL, CRITICAL

class FHIRCommunication(BaseModel):
    resourceType: str = "Communication"
    id: Optional[str] = None
    status: str = "completed"
    subject_reference: str
    topic: str
    sent: datetime = Field(default_factory=datetime.utcnow)
    payload_content: str
    recipient_reference: str
    sender_reference: str

class FHIRTask(BaseModel):
    resourceType: str = "Task"
    id: Optional[str] = None
    status: str = "requested" # requested, in-progress, completed, rejected
    intent: str = "order"
    priority: str = "routine" # routine, urgent, asap, stat
    description: str
    for_patient_reference: str
    authoredOn: datetime = Field(default_factory=datetime.utcnow)
    requester: str
    owner: Optional[str] = None
