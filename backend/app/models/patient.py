from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum
from backend.app.models.base import Base, TimestampMixin
from backend.app.models.enums import RiskTier

class Patient(Base, TimestampMixin):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hospital_id: Mapped[str] = mapped_column(String(64), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    mrn: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    date_of_birth: Mapped[str] = mapped_column(String(32), nullable=False)
    gender: Mapped[str] = mapped_column(String(16), default="unknown")
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(32), default="en")
    
    # Outreach preferences & consent
    consent_for_outreach: Mapped[bool] = mapped_column(Boolean, default=True)
    preferred_call_window_start: Mapped[int] = mapped_column(Integer, default=10) # 10 AM
    preferred_call_window_end: Mapped[int] = mapped_column(Integer, default=16)   # 4 PM
    
    # Clinical risk scoring
    baseline_risk_score: Mapped[float] = mapped_column(Float, default=3.0) # 1.0 to 10.0
    risk_tier: Mapped[RiskTier] = mapped_column(SQLEnum(RiskTier), default=RiskTier.LOW)

    # Relationships
    hospital: Mapped["Hospital"] = relationship("Hospital", back_populates="patients")
    encounters: Mapped[List["Encounter"]] = relationship("Encounter", back_populates="patient", cascade="all, delete-orphan")
    conditions: Mapped[List["Condition"]] = relationship("Condition", back_populates="patient", cascade="all, delete-orphan")
    medications: Mapped[List["Medication"]] = relationship("Medication", back_populates="patient", cascade="all, delete-orphan")
    care_plans: Mapped[List["CarePlan"]] = relationship("CarePlan", back_populates="patient", cascade="all, delete-orphan")
    outreach_tasks: Mapped[List["OutreachTask"]] = relationship("OutreachTask", back_populates="patient", cascade="all, delete-orphan")

class Encounter(Base, TimestampMixin):
    __tablename__ = "encounters"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hospital_id: Mapped[str] = mapped_column(String(64), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(String(64), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    
    encounter_type: Mapped[str] = mapped_column(String(64), default="inpatient")
    admission_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    discharge_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    discharge_disposition: Mapped[str] = mapped_column(String(128), default="Home") # Home, Skilled Nursing, Rehab
    attending_physician: Mapped[str] = mapped_column(String(128), default="Dr. Sarah Lin, MD")
    primary_diagnosis: Mapped[str] = mapped_column(String(255), nullable=False)
    discharge_summary: Mapped[str] = mapped_column(Text, nullable=False)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="encounters")

class Condition(Base, TimestampMixin):
    __tablename__ = "conditions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hospital_id: Mapped[str] = mapped_column(String(64), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(String(64), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    icd10_code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    clinical_status: Mapped[str] = mapped_column(String(32), default="active") # active, resolved

    patient: Mapped["Patient"] = relationship("Patient", back_populates="conditions")

class Medication(Base, TimestampMixin):
    __tablename__ = "medications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hospital_id: Mapped[str] = mapped_column(String(64), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(String(64), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dosage: Mapped[str] = mapped_column(String(128), nullable=False)
    instructions: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="medications")

class CarePlan(Base, TimestampMixin):
    __tablename__ = "care_plans"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hospital_id: Mapped[str] = mapped_column(String(64), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(String(64), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    encounter_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("encounters.id", ondelete="SET NULL"), nullable=True)
    
    protocol_code: Mapped[str] = mapped_column(String(64), nullable=False) # e.g. "CHF_V1", "ORTHO_TKA"
    target_window_hours: Mapped[int] = mapped_column(Integer, default=48)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    red_flag_warnings: Mapped[str] = mapped_column(Text, nullable=False)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="care_plans")
    encounter: Mapped[Optional["Encounter"]] = relationship("Encounter")
