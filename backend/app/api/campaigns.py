from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.app.database import get_db
from backend.app.api.deps import get_tenant_id, get_user_id, get_user_role
from backend.app.models.campaign import OutreachCampaign, OutreachTask
from backend.app.models.patient import Patient
from backend.app.models.audit import AuditLog
from backend.app.models.enums import CampaignStatus, TaskStatus
import json
from backend.app.schemas.campaign import CampaignResponse, CampaignCreate, CampaignUpdate, WorkloadEstimate
from backend.app.schemas.analytics import CampaignReprioritizeRequest
import uuid

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])

@router.get("", response_model=List[CampaignResponse])
async def list_campaigns(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(OutreachCampaign)
        .where(OutreachCampaign.hospital_id == tenant_id)
        .order_by(OutreachCampaign.created_at.desc())
    )
    result = await db.execute(query)
    campaigns = list(result.scalars().all())

    response_items = []
    for c in campaigns:
        # Aggregate task stats
        t_tot = await db.execute(select(func.count(OutreachTask.id)).where(OutreachTask.campaign_id == c.id))
        total_tasks = t_tot.scalar() or 0
        
        t_comp = await db.execute(select(func.count(OutreachTask.id)).where(OutreachTask.campaign_id == c.id, OutreachTask.status == TaskStatus.COMPLETED))
        completed_tasks = t_comp.scalar() or 0

        t_esc = await db.execute(select(func.count(OutreachTask.id)).where(OutreachTask.campaign_id == c.id, OutreachTask.status == TaskStatus.ESCALATED))
        escalated_tasks = t_esc.scalar() or 0

        res_obj = CampaignResponse.model_validate(c)
        res_obj.total_tasks = total_tasks
        res_obj.completed_tasks = completed_tasks
        res_obj.escalated_tasks = escalated_tasks
        response_items.append(res_obj)

    return response_items

@router.post("", response_model=CampaignResponse)
async def create_campaign(
    campaign_data: CampaignCreate,
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    new_id = f"camp-{uuid.uuid4().hex[:8]}"
    camp = OutreachCampaign(
        id=new_id,
        hospital_id=tenant_id,
        name=campaign_data.name,
        description=campaign_data.description,
        target_condition=campaign_data.target_condition,
        followup_window_hours=campaign_data.followup_window_hours,
        calling_hours_start=campaign_data.calling_hours_start,
        calling_hours_end=campaign_data.calling_hours_end,
        max_retries=campaign_data.max_retries,
        priority_level=campaign_data.priority_level,
        allocated_capacity=campaign_data.allocated_capacity,
        status=CampaignStatus.READY
    )
    db.add(camp)

    # Audit log
    db.add(AuditLog(
        id=f"audit-{uuid.uuid4().hex[:10]}",
        hospital_id=tenant_id,
        actor_id=user_id,
        actor_role="CAMPAIGN_MANAGER",
        action="CAMPAIGN_CREATED",
        target_entity="OutreachCampaign",
        target_id=new_id,
        details_json=f'{{"name": "{camp.name}", "condition": "{camp.target_condition}"}}'
    ))

    await db.commit()
    await db.refresh(camp)
    return camp

@router.post("/{campaign_id}/status", response_model=CampaignResponse)
async def change_campaign_status(
    campaign_id: str,
    new_status: CampaignStatus,
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(OutreachCampaign).where(
        OutreachCampaign.id == campaign_id,
        OutreachCampaign.hospital_id == tenant_id
    )
    camp = (await db.execute(query)).scalar_one_or_none()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found in tenant")

    old_status = camp.status
    camp.status = new_status

    # Audit trail
    db.add(AuditLog(
        id=f"audit-{uuid.uuid4().hex[:10]}",
        hospital_id=tenant_id,
        actor_id=user_id,
        actor_role="CAMPAIGN_MANAGER",
        action=f"CAMPAIGN_STATUS_CHANGE_{new_status.value}",
        target_entity="OutreachCampaign",
        target_id=camp.id,
        details_json=f'{{"from": "{old_status.value}", "to": "{new_status.value}"}}'
    ))

    await db.commit()
    await db.refresh(camp)
    return camp

@router.get("/{campaign_id}/workload", response_model=WorkloadEstimate)
async def get_workload_estimate(
    campaign_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(OutreachCampaign).where(
        OutreachCampaign.id == campaign_id,
        OutreachCampaign.hospital_id == tenant_id
    )
    camp = (await db.execute(query)).scalar_one_or_none()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found in tenant")

    # Count eligible patients in hospital matching condition
    pats_q = select(func.count(Patient.id)).where(
        Patient.hospital_id == tenant_id,
        Patient.consent_for_outreach == True
    )
    eligible_count = (await db.execute(pats_q)).scalar() or 0
    expected_calls = int(eligible_count * 1.4) # accounting for ~40% retries/callbacks
    est_hours = round(expected_calls * 0.15 / max(1, camp.allocated_capacity), 1)

    return WorkloadEstimate(
        campaign_id=campaign_id,
        eligible_patients_count=eligible_count,
        estimated_outreach_calls=expected_calls,
        estimated_completion_hours=est_hours,
        capacity_limit=camp.allocated_capacity
    )

@router.patch("/{campaign_id}/reprioritize", response_model=CampaignResponse)
async def reprioritize_campaign(
    campaign_id: str,
    req: CampaignReprioritizeRequest,
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(OutreachCampaign).where(
        OutreachCampaign.id == campaign_id,
        OutreachCampaign.hospital_id == tenant_id
    )
    camp = (await db.execute(query)).scalar_one_or_none()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found in tenant")

    old_pri = camp.priority_level
    old_cap = camp.allocated_capacity
    camp.priority_level = max(1, min(5, req.priority_level))
    camp.allocated_capacity = max(1, min(10, req.allocated_capacity))
    if req.calling_hours_start is not None:
        camp.calling_hours_start = req.calling_hours_start
    if req.calling_hours_end is not None:
        camp.calling_hours_end = req.calling_hours_end

    # Audit trail
    db.add(AuditLog(
        id=f"audit-{uuid.uuid4().hex[:10]}",
        hospital_id=tenant_id,
        actor_id=user_id,
        actor_role="CAMPAIGN_MANAGER",
        action="CAMPAIGN_REPRIORITIZED",
        target_entity="OutreachCampaign",
        target_id=camp.id,
        details_json=json.dumps({
            "priority": {"from": old_pri, "to": camp.priority_level},
            "capacity": {"from": old_cap, "to": camp.allocated_capacity}
        })
    ))

    await db.commit()
    await db.refresh(camp)

    t_tot = (await db.execute(select(func.count(OutreachTask.id)).where(OutreachTask.campaign_id == camp.id))).scalar() or 0
    t_comp = (await db.execute(select(func.count(OutreachTask.id)).where(OutreachTask.campaign_id == camp.id, OutreachTask.status == TaskStatus.COMPLETED))).scalar() or 0
    t_esc = (await db.execute(select(func.count(OutreachTask.id)).where(OutreachTask.campaign_id == camp.id, OutreachTask.status == TaskStatus.ESCALATED))).scalar() or 0

    res_obj = CampaignResponse.model_validate(camp)
    res_obj.total_tasks = t_tot
    res_obj.completed_tasks = t_comp
    res_obj.escalated_tasks = t_esc
    return res_obj

