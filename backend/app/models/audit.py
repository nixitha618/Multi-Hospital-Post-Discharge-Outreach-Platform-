from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, ForeignKey, Text
from backend.app.models.base import Base
from backend.app.time_utils import get_ist_now

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hospital_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=get_ist_now, nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False) # user_id or "SYSTEM" or "AI_AGENT"
    actor_role: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True) # e.g. "CAMPAIGN_PAUSED", "ESCALATION_RESOLVED"
    target_entity: Mapped[str] = mapped_column(String(64), nullable=False) # e.g. "Campaign", "Escalation", "EHR"
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    client_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
