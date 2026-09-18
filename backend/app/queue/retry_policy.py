from datetime import datetime, timedelta
from typing import Optional, Tuple
from backend.app.models.enums import TaskStatus, CallOutcome
from backend.app.models.campaign import OutreachTask
from backend.app.models.organization import Hospital
from backend.app.time_utils import get_ist_now

class RetryPolicy:
    """
    Intelligent Retry and Backoff Policy.
    Calculates next retry timestamps, backoff intervals, and escalation to MANUAL_FOLLOW_UP.
    """

    # Default tiered backoff minutes: 15 min -> 60 min -> 240 min
    DEFAULT_BACKOFF_TIERS = [15, 60, 240]

    @staticmethod
    def calculate_next_retry(
        task: OutreachTask,
        hospital: Hospital,
        outcome: CallOutcome,
        current_time: Optional[datetime] = None
    ) -> Tuple[TaskStatus, Optional[datetime], Optional[str]]:
        """
        Determines the new task status, next scheduled retry time, and transition reason.
        """
        now = current_time or get_ist_now()

        # Terminal outcomes that should NOT retry
        if outcome in [CallOutcome.SUCCESSFUL_COMPLETION, CallOutcome.ESCALATION_TRIGGERED]:
            return TaskStatus.COMPLETED if outcome == CallOutcome.SUCCESSFUL_COMPLETION else TaskStatus.ESCALATED, None, None

        if outcome == CallOutcome.INVALID_NUMBER or outcome == CallOutcome.DECLINED:
            # Patient opted out or number is bad -> immediate human manual follow up
            return TaskStatus.MANUAL_FOLLOW_UP, None, f"Terminal call outcome: {outcome.value}"

        # If maximum retries exceeded -> escalate to manual follow up
        if task.attempts_count >= task.max_retries:
            return TaskStatus.MANUAL_FOLLOW_UP, None, f"Max retries ({task.max_retries}) exceeded after outcome: {outcome.value}"

        # Parse hospital backoff tiers
        tiers = RetryPolicy.DEFAULT_BACKOFF_TIERS
        if hospital.retry_backoff_minutes:
            try:
                tiers = [int(x.strip()) for x in hospital.retry_backoff_minutes.split(",")]
            except Exception:
                tiers = RetryPolicy.DEFAULT_BACKOFF_TIERS

        tier_idx = min(task.attempts_count - 1, len(tiers) - 1)
        tier_idx = max(0, tier_idx)
        backoff_minutes = tiers[tier_idx]

        # Specific adjustments by outcome
        if outcome == CallOutcome.BUSY:
            # Short backoff for busy line: half of current tier (min 10 min)
            backoff_minutes = max(10, backoff_minutes // 2)
        elif outcome == CallOutcome.DROPPED:
            # Dropped call should be retried promptly (e.g. 5-15 mins) to retain context
            backoff_minutes = min(15, backoff_minutes)

        next_retry = now + timedelta(minutes=backoff_minutes)

        # Ensure next retry does not exceed the clinical follow-up deadline
        if next_retry > task.clinical_cutoff_time:
            # If next retry falls after deadline, schedule it as close to deadline as possible (or manual follow up)
            time_left = (task.clinical_cutoff_time - now).total_seconds() / 60.0
            if time_left > 15:
                next_retry = now + timedelta(minutes=int(time_left / 2))
            else:
                return TaskStatus.MANUAL_FOLLOW_UP, None, "Clinical cutoff deadline approaching with no remaining retry window"

        return TaskStatus.RETRY_SCHEDULED, next_retry, f"Retry #{task.attempts_count} scheduled with {backoff_minutes}m backoff after {outcome.value}"

retry_policy = RetryPolicy()
