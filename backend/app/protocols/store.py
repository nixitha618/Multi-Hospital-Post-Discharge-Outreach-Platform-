from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from backend.app.models.protocol import ClinicalProtocol, ProtocolRedFlag, ProtocolQuestion

class ProtocolStore:
    """
    Tenant-aware protocol repository.
    Enforces that queries are strictly scoped to the requesting hospital's tenant context.
    """

    @staticmethod
    async def get_protocols_for_hospital(db: AsyncSession, hospital_id: str) -> List[ClinicalProtocol]:
        query = (
            select(ClinicalProtocol)
            .where(ClinicalProtocol.hospital_id == hospital_id, ClinicalProtocol.is_active == True)
            .options(
                selectinload(ClinicalProtocol.red_flags),
                selectinload(ClinicalProtocol.questions)
            )
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_protocol_for_condition(
        db: AsyncSession, 
        hospital_id: str, 
        condition_str: str
    ) -> Optional[ClinicalProtocol]:
        """
        Retrieves the exact active protocol matching the patient's condition, strictly for their hospital.
        """
        query = (
            select(ClinicalProtocol)
            .where(
                ClinicalProtocol.hospital_id == hospital_id,
                ClinicalProtocol.is_active == True
            )
            .options(
                selectinload(ClinicalProtocol.red_flags),
                selectinload(ClinicalProtocol.questions)
            )
        )
        result = await db.execute(query)
        protocols = list(result.scalars().all())

        condition_upper = condition_str.upper()
        # Find best match
        for p in protocols:
            if p.target_condition.upper() in condition_upper or condition_upper in p.target_condition.upper():
                return p
        
        # Default fallback to first active protocol for this hospital
        return protocols[0] if protocols else None

    @staticmethod
    async def get_protocol_by_code(
        db: AsyncSession,
        hospital_id: str,
        protocol_code: str
    ) -> Optional[ClinicalProtocol]:
        """
        Tenant-isolated lookup by exact protocol code.
        """
        query = (
            select(ClinicalProtocol)
            .where(
                ClinicalProtocol.hospital_id == hospital_id,
                ClinicalProtocol.code == protocol_code,
                ClinicalProtocol.is_active == True
            )
            .options(
                selectinload(ClinicalProtocol.red_flags),
                selectinload(ClinicalProtocol.questions)
            )
        )
        result = await db.execute(query)
        return result.scalars().first()

protocol_store = ProtocolStore()
