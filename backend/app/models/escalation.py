from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Enum as SQLEnum
from backend.app.models.base import Base, TimestampMixin
from backend.app.models.enums import EscalationStatus, UrgencyLevel

class Escalation(Base, TimestampMixin):
    __tablename__ = "escalations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hospital_id: Mapped[str] = mapped_column(String(64), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("outreach_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    call_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("call_records.id", ondelete="SET NULL"), nullable=True)
    patient_id: Mapped[str] = mapped_column(String(64), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(String(64), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)

    status: Mapped[EscalationStatus] = mapped_column(SQLEnum(EscalationStatus), default=EscalationStatus.OPEN, index=True)
    severity: Mapped[UrgencyLevel] = mapped_column(SQLEnum(UrgencyLevel), default=UrgencyLevel.URGENT)
    
    # Clinical reasons & evidence
    trigger_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    clinical_indicators: Mapped[str] = mapped_column(Text, nullable=False) # JSON or bullet points
    protocol_citations: Mapped[str] = mapped_column(Text, nullable=False)
    consensus_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Human in the loop review
    assigned_reviewer_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    assigned_reviewer_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_action: Mapped[Optional[str]] = mapped_column(String(128), nullable=True) # e.g. "Nurse Visit Scheduled", "Physician Callback Completed"
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_by_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Relationships
    task: Mapped["OutreachTask"] = relationship("OutreachTask", back_populates="escalations")
    patient: Mapped[Optional["Patient"]] = relationship("Patient")
    notes: Mapped[List["EscalationNote"]] = relationship("EscalationNote", back_populates="escalation", cascade="all, delete-orphan")

    @property
    def attempts_count(self) -> int:
        return self.task.attempts_count if self.task else 1

    @property
    def max_retries(self) -> int:
        return self.task.max_retries if self.task else 3

class EscalationNote(Base, TimestampMixin):
    __tablename__ = "escalation_notes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    escalation_id: Mapped[str] = mapped_column(String(64), ForeignKey("escalations.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(String(64), nullable=False)
    author_name: Mapped[str] = mapped_column(String(128), nullable=False)
    note_text: Mapped[str] = mapped_column(Text, nullable=False)

    escalation: Mapped["Escalation"] = relationship("Escalation", back_populates="notes")
