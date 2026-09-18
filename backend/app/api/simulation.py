from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database import get_db
from backend.app.api.deps import get_tenant_id
from backend.app.queue.simulator import queue_simulator

router = APIRouter(prefix="/simulation", tags=["Queue Simulation Studio"])

@router.post("/init")
async def init_simulation(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    result = await queue_simulator.initialize_simulation(db, tenant_id)
    return result

@router.post("/step")
async def step_simulation(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    events = await queue_simulator.step_simulation(db, tenant_id)
    return {"step_events": events}
