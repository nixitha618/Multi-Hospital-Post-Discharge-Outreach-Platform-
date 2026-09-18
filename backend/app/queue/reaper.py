from datetime import datetime, timedelta
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.config import settings
from backend.app.models.campaign import OutreachTask
from backend.app.models.audit import AuditLog
from backend.app.models.enums import TaskStatus
from backend.app.time_utils import get_ist_now
import uuid

class StuckWorkerReaper:
    """
    Recovers orphaned tasks and reclaims outbound capacity slots when workers crash or hang.
    """

    @staticmethod
    async def reap_stale_tasks(db: AsyncSession) -> List[str]:
        cutoff = get_ist_now() - timedelta(seconds=settings.WORKER_HEARTBEAT_TIMEOUT_SECONDS)
        
        query = select(OutreachTask).where(
            OutreachTask.status == TaskStatus.CALLING,
            OutreachTask.last_heartbeat_at < cutoff
        )
        result = await db.execute(query)
        stale_tasks = list(result.scalars().all())

        reaped_ids = []
        for task in stale_tasks:
            worker_id = task.assigned_worker_id or "unknown"
            task.assigned_worker_id = None
            task.call_started_at = None
            task.last_heartbeat_at = None
            
            if task.attempts_count >= task.max_retries:
                task.status = TaskStatus.MANUAL_FOLLOW_UP
                task.last_failure_reason = f"Worker {worker_id} crashed/timed out; max retries exceeded"
            else:
                task.status = TaskStatus.RETRY_SCHEDULED
                task.next_retry_at = get_ist_now() + timedelta(minutes=5)
                task.last_failure_reason = f"Worker {worker_id} crashed/timed out; reclaimed by reaper"

            # Create immutable audit entry
            audit = AuditLog(
                id=f"audit-{uuid.uuid4().hex[:12]}",
                hospital_id=task.hospital_id,
                actor_id="STUCK_WORKER_REAPER",
                actor_role="SYSTEM",
                action="WORKER_TIMEOUT_RECOVERED",
                target_entity="OutreachTask",
                target_id=task.id,
                details_json=f'{{"worker_id": "{worker_id}", "new_status": "{task.status.value}"}}'
            )
            db.add(audit)
            reaped_ids.append(task.id)

        if reaped_ids:
            await db.commit()

        return reaped_ids

stuck_worker_reaper = StuckWorkerReaper()
