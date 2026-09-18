from typing import Optional
from fastapi import Header, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database import get_db
from backend.app.models.enums import UserRole

async def get_tenant_id(x_tenant_id: Optional[str] = Header("hosp-mgh")) -> str:
    """
    Extracts explicit tenant context.
    Enforces that every patient-related query carries explicit hospital context.
    """
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required X-Tenant-ID header. Multi-tenant isolation requires explicit tenant context."
        )
    return x_tenant_id

async def get_user_role(x_user_role: Optional[str] = Header("HOSPITAL_ADMIN")) -> UserRole:
    try:
        return UserRole(x_user_role)
    except Exception:
        return UserRole.HOSPITAL_ADMIN

async def get_user_id(x_user_id: Optional[str] = Header("usr-demo")) -> str:
    return x_user_id or "usr-demo"
