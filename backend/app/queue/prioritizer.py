from datetime import datetime, timezone
import math
from typing import Optional
from backend.app.config import settings
from backend.app.models.campaign import OutreachTask, OutreachCampaign
from backend.app.models.patient import Patient
from backend.app.models.organization import Hospital
from backend.app.time_utils import get_ist_now

class QueuePrioritizer:
    """
    Multi-Factor Outbound Queue Prioritizer.
    Calculates dynamic priority score balancing clinical acuity, deadline pressure,
    fairness / anti-starvation, and permitted calling windows.
    """

    @staticmethod
    def is_within_calling_hours(hospital: Hospital, current_dt: Optional[datetime] = None) -> bool:
        """
        Verifies if current time in IST is within permitted calling hours.
        """
        now = current_dt or get_ist_now()
        hour = now.hour
        return hospital.permitted_call_start_hour <= hour < hospital.permitted_call_end_hour

    @staticmethod
    def calculate_priority(
        task: OutreachTask,
        campaign: OutreachCampaign,
        patient: Patient,
        hospital: Hospital,
        current_time: Optional[datetime] = None
    ) -> float:
        now = current_time or get_ist_now()

        # 1. Check scheduled callback override
        # If a patient specifically requested a callback at or before this time, give top priority
        if task.callback_requested_time is not None:
            if now >= task.callback_requested_time:
                # Top priority guarantee for explicit callbacks
                return 999.0 + (task.clinical_risk_score * 0.1)

        # 2. Check hospital calling hours window
        if not QueuePrioritizer.is_within_calling_hours(hospital, now):
            # Suppress priority outside permitted calling window to prevent nuisance calls
            return 0.0

        # 3. Clinical Risk Component (normalized 0 to 100)
        # Clinical risk score ranges from 1.0 (low) to 10.0 (critical)
        risk_component = min(100.0, max(10.0, task.clinical_risk_score * 10.0))

        # 4. Deadline Pressure / Clinical Cutoff Pressure
        # Patients approaching end of clinical follow-up window (e.g. 48h post-discharge)
        # receive non-linear exponential urgency boost
        time_to_cutoff_hours = (task.clinical_cutoff_time - now).total_seconds() / 3600.0
        if time_to_cutoff_hours <= 0:
            # Overdue / deadline expired - maximum urgency
            deadline_component = 100.0
        else:
            # Hyperbolic decay: closer to cutoff -> higher urgency score
            # At 1 hr left: 100 / (1 + 0.5) = 66.6; at 0.5 hr left: 100 / (1 + 0.25) = 80.0
            deadline_component = min(100.0, 100.0 / (1.0 + (0.5 * time_to_cutoff_hours)))

        # 5. Discharge Age / Elapsed Time since Discharge
        # Recent discharges need early engagement
        created_dt = task.created_at or now
        task_age_hours = max(0.0, (now - created_dt).total_seconds() / 3600.0)
        discharge_age_component = min(100.0, 20.0 + (task_age_hours * 2.0))

        # 6. Campaign Priority Level
        # Campaign priority is 1 (low) to 5 (critical)
        campaign_component = float(campaign.priority_level) * 20.0 # 20 to 100

        # 7. Anti-Starvation Mechanism (Aging Boost)
        # Prevents lower-risk patients from remaining perpetually queued behind newer higher-risk patients
        # Generates +1.5 points per hour waiting in queue
        starvation_boost = min(100.0, task_age_hours * 1.5)

        # 8. Retry Penalty (Prevent rapid retry thrashing if backoff elapsed)
        retry_penalty = (task.attempts_count or 0) * 5.0

        # Multi-factor weighted composition
        final_score = (
            (settings.WEIGHT_RISK * risk_component) +
            (settings.WEIGHT_DEADLINE * deadline_component) +
            (settings.WEIGHT_DISCHARGE_AGE * discharge_age_component) +
            (settings.WEIGHT_CAMPAIGN * campaign_component) +
            (settings.WEIGHT_STARVATION * starvation_boost) -
            retry_penalty
        )

        return max(1.0, round(final_score, 2))

prioritizer = QueuePrioritizer()
