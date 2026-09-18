import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select
from backend.app.database import AsyncSessionLocal
from backend.app.time_utils import get_ist_now
from backend.app.queue.concurrency import concurrency_governor
from backend.app.models.campaign import OutreachTask
from backend.app.models.enums import TaskStatus

@pytest.mark.asyncio
async def test_concurrency_capacity_enforcement():
    async with AsyncSessionLocal() as db:
        # Check hospital capacity
        available, active, max_cap = await concurrency_governor.can_reserve_slot(db, "hosp-mgh")
        assert max_cap == 5

        # Create an isolated ephemeral test task so production patient tasks are not modified
        test_task_id = f"task-test-concurrency-{uuid.uuid4().hex[:8]}"
        task = OutreachTask(
            id=test_task_id,
            hospital_id="hosp-mgh",
            campaign_id="camp-mgh-chf-01",
            patient_id="pat-hosp-mgh-001",
            status=TaskStatus.PENDING,
            clinical_risk_score=5.0,
            priority_score=50.0,
            clinical_cutoff_time=get_ist_now() + timedelta(hours=24),
            attempts_count=0,
            max_retries=3,
        )
        db.add(task)
        await db.commit()

        try:
            # Reserve a slot
            success, msg = await concurrency_governor.reserve_call_slot(db, task.id, "worker-unit-test")
            assert success is True

            # Second attempt on same task must fail (cannot double-reserve same task)
            success2, msg2 = await concurrency_governor.reserve_call_slot(db, task.id, "worker-2")
            assert success2 is False
            assert "already in state" in msg2

            # Release slot
            rel = await concurrency_governor.release_call_slot(db, task.id, TaskStatus.COMPLETED)
            assert rel is True
        finally:
            del_t = (await db.execute(select(OutreachTask).where(OutreachTask.id == test_task_id))).scalar_one_or_none()
            if del_t:
                await db.delete(del_t)
                await db.commit()

