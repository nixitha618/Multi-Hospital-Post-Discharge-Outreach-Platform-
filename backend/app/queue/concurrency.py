from datetime import datetime, timedelta
from typing import Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from backend.app.models.campaign import OutreachCampaign, OutreachTask
from backend.app.models.organization import Hospital
from backend.app.models.enums import CampaignStatus, TaskStatus
from backend.app.time_utils import get_ist_now

class ConcurrencyGovernor:
    """
    Centralized Concurrency Governor.
    Enforces tenant-level outbound calling capacity limits atomically across distributed workers.
    """

    @staticmethod
    async def get_active_call_count(db: AsyncSession, hospital_id: str) -> int:
        query = select(func.count(OutreachTask.id)).where(
            OutreachTask.hospital_id == hospital_id,
            OutreachTask.status.in_([TaskStatus.CALLING, TaskStatus.CONNECTED])
        )
        result = await db.execute(query)
        return result.scalar() or 0

    @staticmethod
    async def get_hospital_capacity(db: AsyncSession, hospital_id: str) -> int:
        query = select(Hospital.max_concurrent_calls).where(Hospital.id == hospital_id)
        result = await db.execute(query)
        capacity = result.scalar()
        return capacity if capacity is not None else 5

    @staticmethod
    async def can_reserve_slot(db: AsyncSession, hospital_id: str) -> Tuple[bool, int, int]:
        """
        Checks if a slot is available. Returns (is_available, active_count, max_capacity).
        """
        active_count = await ConcurrencyGovernor.get_active_call_count(db, hospital_id)
        max_capacity = await ConcurrencyGovernor.get_hospital_capacity(db, hospital_id)
        available = active_count < max_capacity
        return available, active_count, max_capacity

    @staticmethod
    async def reserve_call_slot(
        db: AsyncSession,
        task_id: str,
        worker_id: str
    ) -> Tuple[bool, str]:
        """
        Atomically attempts to reserve an outbound call slot for a task.
        Guarantees that concurrency limit is never breached.
        """
        # Load task with row lock intent
        task_query = select(OutreachTask).where(OutreachTask.id == task_id)
        task_res = await db.execute(task_query)
        task = task_res.scalar_one_or_none()

        if not task:
            return False, f"Task {task_id} not found"

        if task.status in [TaskStatus.CALLING, TaskStatus.CONNECTED, TaskStatus.COMPLETED]:
            return False, f"Task {task_id} is already in state {task.status}"

        # Atomic check against active calls for this hospital
        available, active_count, max_capacity = await ConcurrencyGovernor.can_reserve_slot(db, task.hospital_id)
        if not available:
            return False, f"Hospital {task.hospital_id} capacity saturated ({active_count}/{max_capacity} active calls)"

        # Check maximum retries limit
        if task.attempts_count >= task.max_retries:
            return False, f"Task {task_id} has reached maximum outreach attempts ({task.attempts_count}/{task.max_retries})"

        # Reserve slot atomically
        now = get_ist_now()
        task.status = TaskStatus.CALLING
        task.assigned_worker_id = worker_id
        task.call_started_at = now
        task.last_heartbeat_at = now
        task.attempts_count = min(task.attempts_count + 1, task.max_retries)
        task.last_attempt_at = now

        await db.commit()
        await db.refresh(task)
        return True, "Slot successfully reserved"

    @staticmethod
    async def release_call_slot(
        db: AsyncSession,
        task_id: str,
        new_status: TaskStatus,
        failure_reason: Optional[str] = None
    ) -> bool:
        """
        Releases reserved slot and updates task status.
        """
        query = select(OutreachTask).where(OutreachTask.id == task_id)
        res = await db.execute(query)
        task = res.scalar_one_or_none()
        if not task:
            return False

        task.status = new_status
        task.assigned_worker_id = None
        task.call_started_at = None
        task.last_heartbeat_at = None
        if new_status == TaskStatus.COMPLETED:
            task.attempts_count = min(max(1, task.attempts_count), task.max_retries)
        else:
            task.attempts_count = min(task.attempts_count, task.max_retries)
        if failure_reason:
            task.last_failure_reason = failure_reason

        await db.commit()
        return True

    @staticmethod
    async def update_heartbeat(db: AsyncSession, task_id: str, worker_id: str) -> bool:
        query = select(OutreachTask).where(
            OutreachTask.id == task_id,
            OutreachTask.assigned_worker_id == worker_id
        )
        res = await db.execute(query)
        task = res.scalar_one_or_none()
        if not task:
            return False

        task.last_heartbeat_at = get_ist_now()
        await db.commit()
        return True

concurrency_governor = ConcurrencyGovernor()
