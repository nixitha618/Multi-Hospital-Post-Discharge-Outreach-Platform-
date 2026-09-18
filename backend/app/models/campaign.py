from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, Enum as SQLEnum
from backend.app.models.base import Base, TimestampMixin
from backend.app.models.enums import CampaignStatus, TaskStatus

class OutreachCampaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hospital_id: Mapped[str] = mapped_column(String(64), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    target_condition: Mapped[str] = mapped_column(String(128), default="ALL") # e.g. CHF, ORTHO, SEPSIS, ALL
    
    status: Mapped[CampaignStatus] = mapped_column(SQLEnum(CampaignStatus), default=CampaignStatus.DRAFT)
    
    # Clinical windows & constraints
    followup_window_hours: Mapped[int] = mapped_column(Integer, default=48)
    calling_hours_start: Mapped[int] = mapped_column(Integer, default=9)  # 9 AM
    calling_hours_end: Mapped[int] = mapped_column(Integer, default=18)    # 6 PM
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    priority_level: Mapped[int] = mapped_column(Integer, default=3) # 1 (Low) to 5 (Critical)
    
    # Capacity allocation
    allocated_capacity: Mapped[int] = mapped_column(Integer, default=5)
    
    # Schedule dates
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    hospital: Mapped["Hospital"] = relationship("Hospital", back_populates="campaigns")
    tasks: Mapped[List["OutreachTask"]] = relationship("OutreachTask", back_populates="campaign", cascade="all, delete-orphan")

class OutreachTask(Base, TimestampMixin):
    __tablename__ = "outreach_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hospital_id: Mapped[str] = mapped_column(String(64), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(String(64), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(String(64), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    encounter_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("encounters.id", ondelete="SET NULL"), nullable=True)

    status: Mapped[TaskStatus] = mapped_column(SQLEnum(TaskStatus), default=TaskStatus.PENDING, index=True)
    
    # Priority & scheduling metrics
    priority_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    clinical_risk_score: Mapped[float] = mapped_column(Float, default=3.0)
    clinical_cutoff_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    
    # Retry & Callback handling
    attempts_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    callback_requested_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_failure_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Concurrency reservation & worker recovery
    assigned_worker_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    call_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Conversation checkpoint (for resuming dropped calls)
    checkpoint_state_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    campaign: Mapped["OutreachCampaign"] = relationship("OutreachCampaign", back_populates="tasks")
    patient: Mapped["Patient"] = relationship("Patient", back_populates="outreach_tasks")
    encounter: Mapped[Optional["Encounter"]] = relationship("Encounter")
    calls: Mapped[List["CallRecord"]] = relationship("CallRecord", back_populates="task", cascade="all, delete-orphan")
    escalations: Mapped[List["Escalation"]] = relationship("Escalation", back_populates="task", cascade="all, delete-orphan")
