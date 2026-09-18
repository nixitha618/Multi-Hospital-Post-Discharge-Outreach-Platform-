from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, case
from sqlalchemy.orm import selectinload
from backend.app.database import get_db
from backend.app.api.deps import get_tenant_id, get_user_id
from backend.app.models.campaign import OutreachTask, OutreachCampaign
from backend.app.models.organization import Hospital
from backend.app.models.enums import TaskStatus, CampaignStatus
from backend.app.schemas.queue import OutreachTaskResponse, ConcurrencyStatus
from backend.app.time_utils import get_ist_now
from backend.app.queue.concurrency import concurrency_governor
from backend.app.queue.scheduler import queue_scheduler
from backend.app.queue.reaper import stuck_worker_reaper

router = APIRouter(prefix="/queue", tags=["Outbound Queue"])

@router.get("/concurrency", response_model=ConcurrencyStatus)
async def get_queue_concurrency(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    available, active_cnt, max_cap = await concurrency_governor.can_reserve_slot(db, tenant_id)
    utilization = (active_cnt / max_cap * 100.0) if max_cap > 0 else 0.0

    # Count pending tasks
    pending_q = select(func.count(OutreachTask.id)).where(
        OutreachTask.hospital_id == tenant_id,
        OutreachTask.status.in_([TaskStatus.PENDING, TaskStatus.RETRY_SCHEDULED, TaskStatus.CALLBACK_SCHEDULED])
    )
    pending_cnt = (await db.execute(pending_q)).scalar() or 0

    # Find oldest pending task age in IST
    oldest_q = (
        select(OutreachTask.created_at)
        .where(
            OutreachTask.hospital_id == tenant_id,
            OutreachTask.status == TaskStatus.PENDING
        )
        .order_by(OutreachTask.created_at.asc())
        .limit(1)
    )
    oldest_dt = (await db.execute(oldest_q)).scalar_one_or_none()
    oldest_age_mins = None
    if oldest_dt:
        oldest_age_mins = max(0.0, round((get_ist_now() - oldest_dt).total_seconds() / 60.0, 1))

    # Count cutoff-risk tasks (deadline within 4 hours in IST)
    now = get_ist_now()
    four_h = now + timedelta(hours=4)
    risk_q = select(func.count(OutreachTask.id)).where(
        OutreachTask.hospital_id == tenant_id,
        OutreachTask.status.in_([TaskStatus.PENDING, TaskStatus.RETRY_SCHEDULED]),
        OutreachTask.clinical_cutoff_time <= four_h
    )
    cutoff_risk_cnt = (await db.execute(risk_q)).scalar() or 0

    return ConcurrencyStatus(
        hospital_id=tenant_id,
        max_concurrent_capacity=max_cap,
        active_calls_count=active_cnt,
        available_slots=max(0, max_cap - active_cnt),
        utilization_percentage=round(utilization, 1),
        pending_tasks_count=pending_cnt,
        oldest_pending_task_age_minutes=oldest_age_mins,
        cutoff_risk_count=cutoff_risk_cnt
    )

@router.get("/tasks", response_model=List[OutreachTaskResponse])
async def list_queue_tasks(
    status_filter: Optional[str] = Query(None),
    campaign_id: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    # Dynamically update priority scores based on aging, deadlines, and active campaigns
    try:
        await queue_scheduler.update_all_priority_scores(db, tenant_id)
    except Exception:
        pass

    query = (
        select(OutreachTask)
        .where(OutreachTask.hospital_id == tenant_id)
        .options(selectinload(OutreachTask.patient))
    )
    if status_filter:
        query = query.where(OutreachTask.status == TaskStatus(status_filter))
    if campaign_id:
        query = query.where(OutreachTask.campaign_id == campaign_id)

    # Active/actionable tasks (CALLING, recently completed/escalated, PENDING, RETRY_SCHEDULED) prioritized before closed work
    now_ist = get_ist_now()
    recent_cutoff = now_ist - timedelta(minutes=30)
    status_order = case(
        (OutreachTask.status == TaskStatus.CALLING, 1),
        (and_(OutreachTask.status == TaskStatus.COMPLETED, OutreachTask.last_attempt_at >= recent_cutoff), 2),
        (OutreachTask.status == TaskStatus.ESCALATED, 3),
        (OutreachTask.status == TaskStatus.CALLBACK_SCHEDULED, 4),
        (OutreachTask.status == TaskStatus.PENDING, 5),
        (OutreachTask.status == TaskStatus.RETRY_SCHEDULED, 6),
        (OutreachTask.status == TaskStatus.COMPLETED, 7),
        (OutreachTask.status == TaskStatus.MANUAL_FOLLOW_UP, 8),
        else_=9
    )
    query = query.order_by(status_order.asc(), OutreachTask.priority_score.desc()).limit(limit)
    result = await db.execute(query)
    tasks = list(result.scalars().all())
    for t in tasks:
        if t.status == TaskStatus.COMPLETED:
            t.attempts_count = min(max(1, t.attempts_count or 1), t.max_retries)
        elif (t.attempts_count or 0) > t.max_retries:
            t.attempts_count = t.max_retries
    return tasks

@router.post("/reap", response_model=List[str])
async def reap_stalled_workers(
    db: AsyncSession = Depends(get_db)
):
    reaped = await stuck_worker_reaper.reap_stale_tasks(db)
    return reaped

@router.post("/dispatch-next")
async def dispatch_next_slot(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    task, reason = await queue_scheduler.get_next_dispatchable_task(db, tenant_id, allow_paused_override=True)
    if not task:
        return {"dispatched": False, "message": reason}

    # If the campaign was paused, auto-activate it for the operator
    camp = (await db.execute(select(OutreachCampaign).where(OutreachCampaign.id == task.campaign_id))).scalar_one_or_none()
    if camp and camp.status == CampaignStatus.PAUSED:
        camp.status = CampaignStatus.RUNNING
        await db.commit()

    worker_id = f"worker-auto-{get_ist_now().strftime('%H%M%S')}"
    success, msg = await concurrency_governor.reserve_call_slot(db, task.id, worker_id)
    return {
        "dispatched": success,
        "task_id": task.id,
        "patient_id": task.patient_id,
        "priority_score": task.priority_score,
        "worker_id": worker_id,
        "message": msg if success else f"Could not reserve slot: {msg}"
    }
