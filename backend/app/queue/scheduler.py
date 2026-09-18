from datetime import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from backend.app.models.campaign import OutreachCampaign, OutreachTask
from backend.app.models.patient import Patient
from backend.app.models.organization import Hospital
from backend.app.models.enums import CampaignStatus, TaskStatus
from backend.app.queue.prioritizer import prioritizer
from backend.app.queue.concurrency import concurrency_governor
from backend.app.time_utils import get_ist_now

class QueueScheduler:
    """
    Core Queue Scheduler.
    Selects, prioritizes, and schedules the next batch of outbound calls.
    """

    @staticmethod
    async def update_all_priority_scores(db: AsyncSession, hospital_id: str):
        """
        Re-evaluates priority scores dynamically based on aging, deadline pressure, and callbacks.
        """
        now = get_ist_now()
        hosp_res = await db.execute(select(Hospital).where(Hospital.id == hospital_id))
        hospital = hosp_res.scalar_one_or_none()
        if not hospital:
            return

        query = (
            select(OutreachTask)
            .join(OutreachCampaign, OutreachTask.campaign_id == OutreachCampaign.id)
            .join(Patient, OutreachTask.patient_id == Patient.id)
            .where(
                OutreachTask.hospital_id == hospital_id,
                OutreachCampaign.status == CampaignStatus.RUNNING,
                OutreachTask.status.in_([TaskStatus.PENDING, TaskStatus.RETRY_SCHEDULED, TaskStatus.CALLBACK_SCHEDULED])
            )
            .options(
                selectinload(OutreachTask.campaign),
                selectinload(OutreachTask.patient)
            )
        )
        result = await db.execute(query)
        tasks = list(result.scalars().all())

        for task in tasks:
            # Check if retry backoff timer has elapsed
            if task.status == TaskStatus.RETRY_SCHEDULED and task.next_retry_at:
                if now < task.next_retry_at:
                    task.priority_score = 0.0 # Not yet ready to call
                    continue

            score = prioritizer.calculate_priority(task, task.campaign, task.patient, hospital, now)
            task.priority_score = score

        await db.commit()

    @staticmethod
    async def get_next_dispatchable_task(
        db: AsyncSession,
        hospital_id: str,
        allow_paused_override: bool = True
    ) -> tuple[Optional[OutreachTask], str]:
        """
        Fetches the single highest-priority task ready for dispatch, if capacity permits.
        Returns (task, status_reason).
        """
        # 1. Verify capacity available
        available, active, max_cap = await concurrency_governor.can_reserve_slot(db, hospital_id)
        if not available:
            return None, f"Capacity saturated: All outbound lines are occupied ({active}/{max_cap})."

        # 2. Check if any campaigns exist
        camps_q = select(OutreachCampaign).where(OutreachCampaign.hospital_id == hospital_id)
        camps = list((await db.execute(camps_q)).scalars().all())
        if not camps:
            return None, "No active campaigns configured for this hospital."

        # Check running campaigns
        running_camps = [c for c in camps if c.status == CampaignStatus.RUNNING]
        if not running_camps and not allow_paused_override:
            return None, "All outreach campaigns are PAUSED. Click 'Resume Outreach' on a campaign above to dispatch calls."

        # 3. Recalculate priority scores
        await QueueScheduler.update_all_priority_scores(db, hospital_id)

        # 4. Query candidate tasks
        allowed_camp_ids = [c.id for c in running_camps] if (running_camps and not allow_paused_override) else [c.id for c in camps]
        query = (
            select(OutreachTask)
            .where(
                OutreachTask.hospital_id == hospital_id,
                OutreachTask.campaign_id.in_(allowed_camp_ids),
                OutreachTask.status.in_([TaskStatus.PENDING, TaskStatus.RETRY_SCHEDULED, TaskStatus.CALLBACK_SCHEDULED])
            )
            .order_by(OutreachTask.priority_score.desc(), OutreachTask.clinical_risk_score.desc())
            .limit(1)
        )
        result = await db.execute(query)
        task = result.scalars().first()
        if not task:
            return None, "No pending tasks waiting in queue. Click '↺ Reset 25 Patients' to load fresh patients."

        return task, "Task ready for dispatch."

queue_scheduler = QueueScheduler()
