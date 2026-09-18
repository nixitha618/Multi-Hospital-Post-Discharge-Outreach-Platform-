from typing import List, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Text, Enum as SQLEnum
from backend.app.models.base import Base, TimestampMixin
from backend.app.models.enums import HospitalStatus

class Hospital(Base, TimestampMixin):
    __tablename__ = "hospitals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    
    # Operational configuration
    permitted_call_start_hour: Mapped[int] = mapped_column(Integer, default=9)  # 9 AM
    permitted_call_end_hour: Mapped[int] = mapped_column(Integer, default=18)    # 6 PM
    max_concurrent_calls: Mapped[int] = mapped_column(Integer, default=5)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    retry_backoff_minutes: Mapped[str] = mapped_column(String(64), default="15,60,240")
    
    status: Mapped[HospitalStatus] = mapped_column(SQLEnum(HospitalStatus), default=HospitalStatus.READY_FOR_CAMPAIGNS)
    mock_ehr_endpoint: Mapped[str] = mapped_column(String(255), default="mock://ehr-default")
    settings_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    users: Mapped[List["User"]] = relationship("User", back_populates="hospital", cascade="all, delete-orphan")
    patients: Mapped[List["Patient"]] = relationship("Patient", back_populates="hospital", cascade="all, delete-orphan")
    campaigns: Mapped[List["OutreachCampaign"]] = relationship("OutreachCampaign", back_populates="hospital", cascade="all, delete-orphan")
    protocols: Mapped[List["ClinicalProtocol"]] = relationship("ClinicalProtocol", back_populates="hospital", cascade="all, delete-orphan")
