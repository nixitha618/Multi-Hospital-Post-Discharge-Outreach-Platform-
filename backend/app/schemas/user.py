from typing import Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from backend.app.models.enums import UserRole

class UserBase(BaseModel):
    username: str
    full_name: str
    email: str
    role: UserRole
    hospital_id: Optional[str] = None

class UserCreate(UserBase):
    id: Optional[str] = None
    password: Optional[str] = "demo_password"

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    is_active: bool
    created_at: datetime
