from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class ProtocolRedFlagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    indicator: str
    severity: str
    action_required: str
    citation: str

class ProtocolQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sequence_order: int
    category: str
    question_text: str
    expected_observation_key: str
    guidance: Optional[str] = None

class ProtocolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    hospital_id: str
    code: str
    name: str
    target_condition: str
    version: str
    description: str
    is_active: bool
    created_at: datetime
    red_flags: List[ProtocolRedFlagResponse] = []
    questions: List[ProtocolQuestionResponse] = []
