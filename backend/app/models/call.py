from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum
from backend.app.models.base import Base, TimestampMixin
from backend.app.models.enums import CallOutcome, UrgencyLevel

class CallRecord(Base, TimestampMixin):
    __tablename__ = "call_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hospital_id: Mapped[str] = mapped_column(String(64), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("outreach_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(String(64), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(String(64), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)

    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    
    outcome: Mapped[CallOutcome] = mapped_column(SQLEnum(CallOutcome), nullable=False)
    raw_transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # AI Assessments & Triage
    triage_classification: Mapped[Optional[UrgencyLevel]] = mapped_column(SQLEnum(UrgencyLevel), nullable=True)
    clinical_observations_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    protocol_citations_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Escalation & Consensus
    consensus_decision: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    consensus_disagreement: Mapped[bool] = mapped_column(Boolean, default=False)
    consensus_details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    escalation_created: Mapped[bool] = mapped_column(Boolean, default=False)

    # Documentation & EHR Sync
    documentation_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ehr_sync_status: Mapped[str] = mapped_column(String(32), default="NOT_SYNCED") # NOT_SYNCED, SYNCED, FAILED
    ehr_sync_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # AI Observability
    model_name: Mapped[str] = mapped_column(String(64), default="deterministic-healthcare-agent")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    task: Mapped["OutreachTask"] = relationship("OutreachTask", back_populates="calls")
    turns: Mapped[List["CallTurn"]] = relationship("CallTurn", back_populates="call", cascade="all, delete-orphan")

class CallTurn(Base, TimestampMixin):
    __tablename__ = "call_turns"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    call_id: Mapped[str] = mapped_column(String(64), ForeignKey("call_records.id", ondelete="CASCADE"), nullable=False, index=True)
    speaker: Mapped[str] = mapped_column(String(16), nullable=False) # "AGENT" or "PATIENT"
    text: Mapped[str] = mapped_column(Text, nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, default=0)
    intent: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    call: Mapped["CallRecord"] = relationship("CallRecord", back_populates="turns")
