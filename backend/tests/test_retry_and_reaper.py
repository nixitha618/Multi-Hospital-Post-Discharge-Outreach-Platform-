import pytest
from datetime import datetime, timedelta
from backend.app.database import AsyncSessionLocal
from backend.app.time_utils import get_ist_now
from backend.app.models.campaign import OutreachTask
from backend.app.models.organization import Hospital
from backend.app.models.enums import TaskStatus, CallOutcome
from backend.app.queue.retry_policy import retry_policy
from backend.app.queue.reaper import stuck_worker_reaper

def test_retry_backoff_tiers():
    hosp = Hospital(
        id="hosp-test",
        name="Test",
        code="TH",
        contact_email="test@th.org",
        contact_phone="555",
        retry_backoff_minutes="15,60,240"
    )
    now = datetime(2026, 9, 18, 10, 0, 0)
    cutoff = now + timedelta(hours=48)

    # Attempt 1: busy outcome
    task = OutreachTask(
        id="task-1",
        hospital_id="hosp-test",
        campaign_id="camp-1",
        patient_id="pat-1",
        attempts_count=1,
        max_retries=3,
        clinical_cutoff_time=cutoff
    )
    status, nxt, reason = retry_policy.calculate_next_retry(task, hosp, CallOutcome.BUSY, now)
    assert status == TaskStatus.RETRY_SCHEDULED
    assert nxt is not None
    # Busy outcome halves tier (15//2 = 7, min 10 -> 10 mins)
    diff_mins = (nxt - now).total_seconds() / 60.0
    assert diff_mins >= 10.0

def test_max_retries_transition_to_manual_followup():
    hosp = Hospital(id="hosp-test", name="Test", code="TH", contact_email="test@th.org", contact_phone="555")
    now = datetime(2026, 9, 18, 10, 0, 0)
    cutoff = now + timedelta(hours=48)

    # Attempt 3: reached max_retries
    task = OutreachTask(
        id="task-1",
        hospital_id="hosp-test",
        campaign_id="camp-1",
        patient_id="pat-1",
        attempts_count=3,
        max_retries=3,
        clinical_cutoff_time=cutoff
    )
    status, nxt, reason = retry_policy.calculate_next_retry(task, hosp, CallOutcome.NO_ANSWER, now)
    assert status == TaskStatus.MANUAL_FOLLOW_UP
    assert nxt is None
    assert "Max retries (3) exceeded" in reason

@pytest.mark.asyncio
async def test_stuck_worker_reaper_recovery():
    import uuid
    async with AsyncSessionLocal() as db:
        # Create an orphaned task in CALLING state with stale heartbeat (200 seconds ago)
        stale_time = get_ist_now() - timedelta(seconds=200)
        unique_id = f"task-stuck-{uuid.uuid4().hex[:8]}"
        task = OutreachTask(
            id=unique_id,
            hospital_id="hosp-mgh",
            campaign_id="camp-mgh-chf-01",
            patient_id="pat-hosp-mgh-002",
            status=TaskStatus.CALLING,
            assigned_worker_id="crashed-worker-99",
            call_started_at=stale_time,
            last_heartbeat_at=stale_time,
            clinical_cutoff_time=get_ist_now() + timedelta(hours=24),
            attempts_count=1,
            max_retries=3
        )
        db.add(task)
        await db.commit()

        # Run reaper
        reaped = await stuck_worker_reaper.reap_stale_tasks(db)
        assert unique_id in reaped

        # Verify task was recovered and slot freed
        await db.refresh(task)
        assert task.status == TaskStatus.RETRY_SCHEDULED
        assert task.assigned_worker_id is None
        assert "crashed/timed out" in task.last_failure_reason
