from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.database import get_db
from backend.app.models.organization import Hospital
from backend.app.schemas.hospital import HospitalResponse, HospitalCreate, HospitalUpdate

router = APIRouter(prefix="/hospitals", tags=["Hospitals"])

@router.get("", response_model=List[HospitalResponse])
async def list_hospitals(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Hospital).order_by(Hospital.name))
    return list(result.scalars().all())

@router.get("/{hospital_id}", response_model=HospitalResponse)
async def get_hospital(hospital_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Hospital).where(Hospital.id == hospital_id))
    hosp = result.scalar_one_or_none()
    if not hosp:
        raise HTTPException(status_code=404, detail="Hospital tenant not found")
    return hosp

@router.patch("/{hospital_id}", response_model=HospitalResponse)
async def update_hospital(hospital_id: str, update_data: HospitalUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Hospital).where(Hospital.id == hospital_id))
    hosp = result.scalar_one_or_none()
    if not hosp:
        raise HTTPException(status_code=404, detail="Hospital tenant not found")
    
    for field, val in update_data.model_dump(exclude_unset=True).items():
        setattr(hosp, field, val)

    await db.commit()
    await db.refresh(hosp)
    return hosp
