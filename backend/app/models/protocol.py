from typing import List, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Boolean, ForeignKey, Text
from backend.app.models.base import Base, TimestampMixin

class ClinicalProtocol(Base, TimestampMixin):
    __tablename__ = "clinical_protocols"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hospital_id: Mapped[str] = mapped_column(String(64), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True) # e.g. PROTO-CHF-01
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_condition: Mapped[str] = mapped_column(String(128), nullable=False) # e.g. CHF, TKA, SEPSIS
    version: Mapped[str] = mapped_column(String(32), default="1.0")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    hospital: Mapped["Hospital"] = relationship("Hospital", back_populates="protocols")
    red_flags: Mapped[List["ProtocolRedFlag"]] = relationship("ProtocolRedFlag", back_populates="protocol", cascade="all, delete-orphan")
    questions: Mapped[List["ProtocolQuestion"]] = relationship("ProtocolQuestion", back_populates="protocol", cascade="all, delete-orphan")

class ProtocolRedFlag(Base, TimestampMixin):
    __tablename__ = "protocol_red_flags"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    protocol_id: Mapped[str] = mapped_column(String(64), ForeignKey("clinical_protocols.id", ondelete="CASCADE"), nullable=False, index=True)
    indicator: Mapped[str] = mapped_column(String(255), nullable=False) # e.g. "Weight gain >= 3 lbs in 2 days"
    severity: Mapped[str] = mapped_column(String(32), default="URGENT") # URGENT, CONCERNING
    action_required: Mapped[str] = mapped_column(String(255), default="Immediate human nurse escalation")
    citation: Mapped[str] = mapped_column(String(255), nullable=False) # Reference code/title

    protocol: Mapped["ClinicalProtocol"] = relationship("ClinicalProtocol", back_populates="red_flags")

class ProtocolQuestion(Base, TimestampMixin):
    __tablename__ = "protocol_questions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    protocol_id: Mapped[str] = mapped_column(String(64), ForeignKey("clinical_protocols.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence_order: Mapped[int] = mapped_column(Integer, default=1)
    category: Mapped[str] = mapped_column(String(64), default="symptom") # greeting, symptom, medication, follow_up
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    expected_observation_key: Mapped[str] = mapped_column(String(64), nullable=False) # e.g. "shortness_of_breath"
    guidance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    protocol: Mapped["ClinicalProtocol"] = relationship("ClinicalProtocol", back_populates="questions")
