from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Enum as SQLEnum
from backend.app.models.base import Base, TimestampMixin
from backend.app.models.enums import UserRole

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hospital_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), default="demo_secret_hash")
    is_active: Mapped[bool] = mapped_column(default=True)

    hospital: Mapped[Optional["Hospital"]] = relationship("Hospital", back_populates="users")
