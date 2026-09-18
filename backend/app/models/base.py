from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime
from backend.app.time_utils import get_ist_now

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_ist_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=get_ist_now, onupdate=get_ist_now)
