from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database import get_db
from backend.app.api.deps import get_tenant_id
from backend.app.protocols.store import protocol_store
from backend.app.schemas.protocol import ProtocolResponse

router = APIRouter(prefix="/protocols", tags=["Clinical Protocols"])

@router.get("", response_model=List[ProtocolResponse])
async def get_tenant_protocols(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    protocols = await protocol_store.get_protocols_for_hospital(db, tenant_id)
    return protocols
