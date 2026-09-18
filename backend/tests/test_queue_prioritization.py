import pytest
from datetime import datetime, timedelta
from backend.app.models.campaign import OutreachTask, OutreachCampaign
from backend.app.models.patient import Patient
from backend.app.models.organization import Hospital
from backend.app.queue.prioritizer import prioritizer

def test_deadline_pressure_boost():
    now = datetime(2026, 9, 18, 12, 0, 0) # 12 PM (during calling hours)

    hosp = Hospital(
        id="hosp-test",
        name="Test Hospital",
        code="TH",
        contact_email="test@th.org",
        contact_phone="555-0000",
        permitted_call_start_hour=9,
        permitted_call_end_hour=18
    )

    camp = OutreachCampaign(
        id="camp-1",
        hospital_id="hosp-test",
        name="Test",
        description="",
        priority_level=3
    )

    patient = Patient(
        id="pat-1",
        hospital_id="hosp-test",
        mrn="MRN-1",
        first_name="Alice",
        last_name="Smith",
        date_of_birth="1950-01-01",
        phone_number="555-0101",
        consent_for_outreach=True
    )

    # Task A: High clinical risk (8.0) but has 30 hours until cutoff
    task_a = OutreachTask(
        id="task-a",
        hospital_id="hosp-test",
        campaign_id="camp-1",
        patient_id="pat-1",
        clinical_risk_score=8.0,
        clinical_cutoff_time=now + timedelta(hours=30),
        created_at=now - timedelta(hours=2)
    )

    # Task B: Moderate clinical risk (5.0) but clinical cutoff is in 45 minutes!
    task_b = OutreachTask(
        id="task-b",
        hospital_id="hosp-test",
        campaign_id="camp-1",
        patient_id="pat-1",
        clinical_risk_score=5.0,
        clinical_cutoff_time=now + timedelta(minutes=45),
        created_at=now - timedelta(hours=2)
    )

    score_a = prioritizer.calculate_priority(task_a, camp, patient, hosp, now)
    score_b = prioritizer.calculate_priority(task_b, camp, patient, hosp, now)

    # Task B should have significant deadline pressure boost
    assert score_b > score_a, f"Expected impending deadline Task B ({score_b}) to surpass Task A ({score_a})"

def test_callback_scheduled_override():
    now = datetime(2026, 9, 18, 14, 0, 0)
    hosp = Hospital(
        id="hosp-test",
        name="Test Hospital",
        code="TH",
        contact_email="test@th.org",
        contact_phone="555-0000",
        permitted_call_start_hour=9,
        permitted_call_end_hour=18
    )
    camp = OutreachCampaign(id="camp-1", hospital_id="hosp-test", name="Test", description="", priority_level=3)
    patient = Patient(id="pat-1", hospital_id="hosp-test", mrn="MRN-1", first_name="Bob", last_name="Jones", date_of_birth="1960-01-01", phone_number="555-0102")

    task_cb = OutreachTask(
        id="task-cb",
        hospital_id="hosp-test",
        campaign_id="camp-1",
        patient_id="pat-1",
        clinical_risk_score=4.0,
        clinical_cutoff_time=now + timedelta(hours=20),
        callback_requested_time=now - timedelta(minutes=2) # Due now
    )

    score_cb = prioritizer.calculate_priority(task_cb, camp, patient, hosp, now)
    assert score_cb >= 999.0, f"Expected top priority for scheduled callback, got {score_cb}"
