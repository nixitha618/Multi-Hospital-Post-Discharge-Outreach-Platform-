from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.database import get_db
from backend.app.api.deps import get_tenant_id
from backend.app.models.audit import AuditLog
from backend.app.schemas.audit import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["Audit Trail"])

@router.get("", response_model=List[AuditLogResponse])
async def list_audit_logs(
    limit: int = Query(50, le=200),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(AuditLog)
        .where(AuditLog.hospital_id == tenant_id)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())
