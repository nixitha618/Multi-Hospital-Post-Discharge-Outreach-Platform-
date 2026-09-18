import uuid
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from backend.app.models.campaign import OutreachCampaign, OutreachTask
from backend.app.models.patient import Patient, Encounter
from backend.app.models.organization import Hospital
from backend.app.models.call import CallRecord
from backend.app.models.escalation import Escalation
from backend.app.models.enums import CampaignStatus, TaskStatus, CallOutcome, UrgencyLevel, RiskTier
from backend.app.queue.concurrency import concurrency_governor
from backend.app.queue.prioritizer import prioritizer
from backend.app.queue.retry_policy import retry_policy
from backend.app.queue.reaper import stuck_worker_reaper
from backend.app.time_utils import get_ist_now

class QueueSimulator:
    """
    Queue Simulation Engine for 25 mock patients.
    Demonstrates constrained concurrency, dynamic multi-factor prioritization,
    outcomes, retries, callbacks, and escalations.
    """

    @staticmethod
    async def initialize_simulation(db: AsyncSession, hospital_id: str) -> Dict[str, Any]:
        """
        Creates or resets a 25-patient simulation cohort for the given hospital.
        """
        # Ensure hospital exists
        hosp = (await db.execute(select(Hospital).where(Hospital.id == hospital_id))).scalar_one_or_none()
        if not hosp:
            hosp = Hospital(
                id=hospital_id,
                name="Metro General Hospital (Simulation)",
                code="MGH-SIM",
                contact_email="outreach@mgh-sim.health",
                contact_phone="617-555-0100",
                max_concurrent_calls=3, # Constrained capacity for vivid simulation
                max_retries=3
            )
            db.add(hosp)
            await db.commit()

        # Find or create Simulation Campaign
        camp_query = select(OutreachCampaign).where(
            OutreachCampaign.hospital_id == hospital_id,
            OutreachCampaign.name == "Simulation Outreach Campaign"
        )
        camp = (await db.execute(camp_query)).scalar_one_or_none()
        if not camp:
            camp = OutreachCampaign(
                id=f"camp-sim-{uuid.uuid4().hex[:8]}",
                hospital_id=hospital_id,
                name="Simulation Outreach Campaign",
                description="Live 25-patient simulation demonstrating concurrency, prioritization, and safety triage.",
                target_condition="MIXED",
                status=CampaignStatus.RUNNING,
                followup_window_hours=48,
                priority_level=4,
                allocated_capacity=3
            )
            db.add(camp)
        else:
            camp.status = CampaignStatus.RUNNING
        await db.commit()
        await db.refresh(camp)

        # Clear previous simulation tasks for this campaign
        del_tasks = select(OutreachTask).where(OutreachTask.campaign_id == camp.id)
        existing_tasks = list((await db.execute(del_tasks)).scalars().all())
        for t in existing_tasks:
            await db.delete(t)
        await db.commit()

        now = get_ist_now()

        # Patient profiles matrix (25 varied archetypes)
        profiles = [
            # High Risk & Urgent Deadline (Cutoff in 1-2 hours)
            {"name": "Arthur Pendelton", "age": 74, "dx": "CHF Exacerbation", "risk": 8.8, "cutoff_h": 1.5, "cond": "CHF", "outcome_pref": "ESCALATION"},
            {"name": "Beatrice Gomez", "age": 69, "dx": "Total Knee Arthroplasty", "risk": 7.5, "cutoff_h": 2.0, "cond": "ORTHO", "outcome_pref": "ESCALATION"},
            {"name": "Charles Vance", "age": 62, "dx": "Severe Sepsis Recovery", "risk": 9.2, "cutoff_h": 1.0, "cond": "SEPSIS", "outcome_pref": "ESCALATION"},
            
            # High Risk with Ample Time (Cutoff in 30-40 hours) -> Tests that urgency ramp correctly prioritizes impending deadlines!
            {"name": "Dorothy Chen", "age": 79, "dx": "CHF Decompensation", "risk": 9.0, "cutoff_h": 36.0, "cond": "CHF", "outcome_pref": "SUCCESS"},
            {"name": "Edward Miller", "age": 71, "dx": "Sepsis Secondary to UTI", "risk": 8.4, "cutoff_h": 40.0, "cond": "SEPSIS", "outcome_pref": "SUCCESS"},
            
            # Moderate Risk (Cutoff in 4-8 hours)
            {"name": "Florence Nightingale Jr.", "age": 55, "dx": "Bilateral TKA", "risk": 5.5, "cutoff_h": 6.0, "cond": "ORTHO", "outcome_pref": "SUCCESS"},
            {"name": "George Washington IV", "age": 66, "dx": "Mild CHF", "risk": 6.0, "cutoff_h": 8.0, "cond": "CHF", "outcome_pref": "CALLBACK"},
            {"name": "Harriet Tubman III", "age": 59, "dx": "Urosepsis Recovery", "risk": 6.2, "cutoff_h": 5.0, "cond": "SEPSIS", "outcome_pref": "NO_ANSWER"},
            {"name": "Ian Malcolm", "age": 48, "dx": "Post-PCI Stent Placement", "risk": 5.8, "cutoff_h": 7.0, "cond": "CHF", "outcome_pref": "BUSY"},
            {"name": "Julia Roberts-Sim", "age": 61, "dx": "Hip Arthroplasty", "risk": 5.0, "cutoff_h": 4.5, "cond": "ORTHO", "outcome_pref": "SUCCESS"},

            # Low Risk with Near Deadline (Tests anti-starvation / deadline cutoff prioritization)
            {"name": "Kevin Bacon-Sim", "age": 35, "dx": "General Post-Op Laparoscopy", "risk": 2.5, "cutoff_h": 0.8, "cond": "CHF", "outcome_pref": "SUCCESS"},
            {"name": "Laura Croft-Sim", "age": 29, "dx": "Uncomplicated Appendectomy", "risk": 2.0, "cutoff_h": 1.2, "cond": "ORTHO", "outcome_pref": "SUCCESS"},

            # Standard cohort (13 remaining cases with mixed conditions & outcomes)
            {"name": "Marcus Aurelius", "age": 70, "dx": "CHF Class II", "risk": 6.5, "cutoff_h": 24.0, "cond": "CHF", "outcome_pref": "SUCCESS"},
            {"name": "Nancy Drew", "age": 52, "dx": "TKA Left Knee", "risk": 4.8, "cutoff_h": 20.0, "cond": "ORTHO", "outcome_pref": "DROPPED"},
            {"name": "Oliver Twist", "age": 44, "dx": "Pneumonia Sepsis", "risk": 5.2, "cutoff_h": 18.0, "cond": "SEPSIS", "outcome_pref": "SUCCESS"},
            {"name": "Patricia Star", "age": 63, "dx": "CHF", "risk": 7.0, "cutoff_h": 22.0, "cond": "CHF", "outcome_pref": "SUCCESS"},
            {"name": "Quentin Tarantino", "age": 60, "dx": "Total Hip Replacement", "risk": 4.5, "cutoff_h": 26.0, "cond": "ORTHO", "outcome_pref": "SUCCESS"},
            {"name": "Rachel Green", "age": 39, "dx": "Cellulitis Sepsis", "risk": 4.0, "cutoff_h": 30.0, "cond": "SEPSIS", "outcome_pref": "CALLBACK"},
            {"name": "Steven Strange", "age": 51, "dx": "Bilateral Knee Surgery", "risk": 5.6, "cutoff_h": 14.0, "cond": "ORTHO", "outcome_pref": "SUCCESS"},
            {"name": "Tina Turner", "age": 73, "dx": "CHF with HTN", "risk": 7.8, "cutoff_h": 16.0, "cond": "CHF", "outcome_pref": "ESCALATION"},
            {"name": "Ulysses Grant", "age": 68, "dx": "Post-ICU Sepsis", "risk": 6.9, "cutoff_h": 12.0, "cond": "SEPSIS", "outcome_pref": "NO_ANSWER"},
            {"name": "Victoria Wood", "age": 58, "dx": "Joint Replacement", "risk": 4.2, "cutoff_h": 28.0, "cond": "ORTHO", "outcome_pref": "SUCCESS"},
            {"name": "Walter White", "age": 56, "dx": "CHF & Respiratory", "risk": 8.0, "cutoff_h": 10.0, "cond": "CHF", "outcome_pref": "BUSY"},
            {"name": "Xena Warrior", "age": 42, "dx": "Orthopedic Repair", "risk": 3.2, "cutoff_h": 32.0, "cond": "ORTHO", "outcome_pref": "SUCCESS"},
            {"name": "Yosef Ben-David", "age": 65, "dx": "Severe Sepsis Follow-up", "risk": 7.4, "cutoff_h": 15.0, "cond": "SEPSIS", "outcome_pref": "SUCCESS"}
        ]

        created_tasks = []
        for i, p in enumerate(profiles):
            pat_id = f"pat-sim-{i+1:03d}"
            # Ensure patient exists
            pat = (await db.execute(select(Patient).where(Patient.id == pat_id))).scalar_one_or_none()
            if not pat:
                names = p["name"].split(" ")
                first, last = names[0], " ".join(names[1:])
                tier = RiskTier.CRITICAL if p["risk"] >= 8.0 else (RiskTier.HIGH if p["risk"] >= 6.0 else RiskTier.MODERATE)
                pat = Patient(
                    id=pat_id,
                    hospital_id=hospital_id,
                    mrn=f"MRN-SIM-{1000+i}",
                    first_name=first,
                    last_name=last,
                    date_of_birth="1960-05-12",
                    gender="M" if i % 2 == 0 else "F",
                    phone_number=f"555-01{i+20:02d}",
                    preferred_language="en",
                    consent_for_outreach=True,
                    baseline_risk_score=p["risk"],
                    risk_tier=tier
                )
                db.add(pat)
                await db.flush()

            task_id = f"task-sim-{i+1:03d}"
            cutoff_dt = now + timedelta(hours=p["cutoff_h"])
            
            task = OutreachTask(
                id=task_id,
                hospital_id=hospital_id,
                campaign_id=camp.id,
                patient_id=pat.id,
                status=TaskStatus.PENDING,
                clinical_risk_score=p["risk"],
                clinical_cutoff_time=cutoff_dt,
                max_retries=3,
                checkpoint_state_json=f'{{"outcome_pref": "{p["outcome_pref"]}", "cond": "{p["cond"]}"}}'
            )
            # Calculate initial priority score
            task.priority_score = prioritizer.calculate_priority(task, camp, pat, hosp, now)
            db.add(task)
            created_tasks.append(task)

        await db.commit()
        return {
            "campaign_id": camp.id,
            "tasks_count": len(created_tasks),
            "concurrency_limit": hosp.max_concurrent_calls,
            "message": "Initialized 25-patient simulation cohort with varied acuity and cutoff deadlines."
        }

    @staticmethod
    async def step_simulation(db: AsyncSession, hospital_id: str) -> List[Dict[str, Any]]:
        """
        Advances the simulation by one operational step:
        1. Reaps any dead-man worker timeouts.
        2. Progresses existing CALLING tasks to outcomes (SUCCESS, ESCALATION, BUSY, NO_ANSWER, DROPPED, CALLBACK).
        3. Recalculates priority scores.
        4. Fills open concurrency slots with highest-priority ready tasks.
        """
        now = get_ist_now()
        events = []

        # 1. Reaper check
        reaped = await stuck_worker_reaper.reap_stale_tasks(db)
        if reaped:
            events.append({
                "type": "REAPER",
                "message": f"Heartbeat reaper recovered {len(reaped)} stalled call(s): {', '.join(reaped)}"
            })

        hosp_query = select(Hospital).where(Hospital.id == hospital_id)
        hospital = (await db.execute(hosp_query)).scalar_one_or_none()
        if not hospital:
            return [{"error": "Hospital not found"}]

        # 2. Progress active calls (CALLING -> Outcome)
        active_query = (
            select(OutreachTask)
            .where(
                OutreachTask.hospital_id == hospital_id,
                OutreachTask.status == TaskStatus.CALLING
            )
        )
        active_tasks = list((await db.execute(active_query)).scalars().all())

        for task in active_tasks:
            # Simulate progression to terminal or retry outcome
            pref = "SUCCESS"
            if task.checkpoint_state_json:
                import json
                try:
                    meta = json.loads(task.checkpoint_state_json)
                    pref = meta.get("outcome_pref", "SUCCESS")
                except Exception:
                    pref = "SUCCESS"

            # Outcome dispatch
            if pref == "ESCALATION":
                outcome = CallOutcome.ESCALATION_TRIGGERED
                task.status = TaskStatus.ESCALATED
                # Create escalation record
                esc = Escalation(
                    id=f"esc-{uuid.uuid4().hex[:8]}",
                    hospital_id=hospital_id,
                    task_id=task.id,
                    patient_id=task.patient_id,
                    campaign_id=task.campaign_id,
                    severity=UrgencyLevel.URGENT,
                    trigger_reason="Severe clinical red-flag: Acute Dyspnea & 4 lb rapid fluid gain",
                    clinical_indicators="Patient reports 4 lb weight gain over 48h and inability to sleep lying flat.",
                    protocol_citations="AHA/ACC Heart Failure Protocol Section 4.2",
                    consensus_rationale="Evaluator A (Clinical) and Evaluator B (Protocol) both flagged URGENT. Disagreement: None."
                )
                db.add(esc)
                events.append({
                    "task_id": task.id,
                    "event": "ESCALATION_TRIGGERED",
                    "reason": "AI triage detected severe red-flag; immediate human clinical review initiated.",
                    "status": "ESCALATED"
                })
            elif pref == "BUSY":
                outcome = CallOutcome.BUSY
                new_st, nxt, rsn = retry_policy.calculate_next_retry(task, hospital, outcome, now)
                task.status = new_st
                task.next_retry_at = nxt
                events.append({
                    "task_id": task.id,
                    "event": "CALL_BUSY",
                    "reason": f"Line busy. {rsn}",
                    "status": new_st.value
                })
            elif pref == "NO_ANSWER":
                outcome = CallOutcome.NO_ANSWER
                new_st, nxt, rsn = retry_policy.calculate_next_retry(task, hospital, outcome, now)
                task.status = new_st
                task.next_retry_at = nxt
                events.append({
                    "task_id": task.id,
                    "event": "CALL_NO_ANSWER",
                    "reason": f"No answer. {rsn}",
                    "status": new_st.value
                })
            elif pref == "DROPPED":
                outcome = CallOutcome.DROPPED
                new_st, nxt, rsn = retry_policy.calculate_next_retry(task, hospital, outcome, now)
                task.status = new_st
                task.next_retry_at = nxt
                events.append({
                    "task_id": task.id,
                    "event": "CALL_DROPPED",
                    "reason": "Call dropped mid-conversation. Checkpoint saved for next attempt.",
                    "status": new_st.value
                })
            elif pref == "CALLBACK":
                outcome = CallOutcome.CALLBACK_REQUESTED
                task.status = TaskStatus.CALLBACK_SCHEDULED
                task.callback_requested_time = now + timedelta(minutes=30)
                events.append({
                    "task_id": task.id,
                    "event": "CALLBACK_REQUESTED",
                    "reason": "Patient requested callback in 30 mins; scheduled explicitly.",
                    "status": "CALLBACK_SCHEDULED"
                })
            else:
                outcome = CallOutcome.SUCCESSFUL_COMPLETION
                task.status = TaskStatus.COMPLETED
                events.append({
                    "task_id": task.id,
                    "event": "CALL_COMPLETED",
                    "reason": "Successful outreach completed; patient reports stable recovery.",
                    "status": "COMPLETED"
                })

            task.assigned_worker_id = None
            task.call_started_at = None
            task.last_heartbeat_at = None

        await db.commit()

        # 3. Check capacity & dispatch new tasks
        available_slots, active_cnt, max_cap = await concurrency_governor.can_reserve_slot(db, hospital_id)
        open_slots = max_cap - active_cnt

        if open_slots > 0:
            # Re-score waiting tasks
            camp_res = await db.execute(
                select(OutreachCampaign).where(
                    OutreachCampaign.hospital_id == hospital_id,
                    OutreachCampaign.status == CampaignStatus.RUNNING
                )
            )
            campaigns = {c.id: c for c in camp_res.scalars().all()}

            waiting_query = (
                select(OutreachTask)
                .where(
                    OutreachTask.hospital_id == hospital_id,
                    OutreachTask.status.in_([TaskStatus.PENDING, TaskStatus.RETRY_SCHEDULED, TaskStatus.CALLBACK_SCHEDULED])
                )
            )
            waiting_tasks = list((await db.execute(waiting_query)).scalars().all())

            # Score and sort
            candidate_list = []
            for t in waiting_tasks:
                if t.status == TaskStatus.RETRY_SCHEDULED and t.next_retry_at and now < t.next_retry_at:
                    continue # backoff active
                c = campaigns.get(t.campaign_id)
                if not c:
                    continue
                # Get patient
                pat = (await db.execute(select(Patient).where(Patient.id == t.patient_id))).scalar_one_or_none()
                if not pat:
                    continue
                score = prioritizer.calculate_priority(t, c, pat, hospital, now)
                t.priority_score = score
                candidate_list.append(t)

            candidate_list.sort(key=lambda x: x.priority_score, reverse=True)

            dispatched_count = 0
            for t in candidate_list[:open_slots]:
                worker_id = f"sim-worker-{dispatched_count+1}"
                success, msg = await concurrency_governor.reserve_call_slot(db, t.id, worker_id)
                if success:
                    dispatched_count += 1
                    events.append({
                        "task_id": t.id,
                        "event": "CALL_DISPATCHED",
                        "priority_score": t.priority_score,
                        "worker_id": worker_id,
                        "reason": f"Dispatched into open slot (Score: {t.priority_score:.1f})",
                        "status": "CALLING"
                    })

        await db.commit()
        return events

queue_simulator = QueueSimulator()
