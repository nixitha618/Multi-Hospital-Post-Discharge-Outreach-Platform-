import uuid
import random
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.models.organization import Hospital
from backend.app.models.user import User
from backend.app.models.patient import Patient, Encounter, Condition, Medication, CarePlan
from backend.app.models.campaign import OutreachCampaign, OutreachTask
from backend.app.models.protocol import ClinicalProtocol, ProtocolRedFlag, ProtocolQuestion
from backend.app.models.escalation import Escalation, EscalationNote
from backend.app.models.call import CallRecord, CallTurn
from backend.app.models.audit import AuditLog
from backend.app.models.enums import (
    UserRole, HospitalStatus, CampaignStatus, TaskStatus,
    RiskTier, CallOutcome, EscalationStatus, UrgencyLevel
)
from backend.app.protocols.default_protocols import DEFAULT_PROTOCOLS
from backend.app.queue.prioritizer import prioritizer
from backend.app.time_utils import get_ist_now

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Kenneth", "Dorothy", "Kevin", "Carol", "Brian", "Amanda", "George", "Melissa"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores"
]

HOSPITALS_SEED = [
    {
        "id": "hosp-mgh",
        "name": "Metro General Hospital",
        "code": "MGH",
        "timezone": "America/New_York",
        "contact_email": "admin@mgh.health",
        "contact_phone": "617-555-0100",
        "permitted_call_start_hour": 9,
        "permitted_call_end_hour": 18,
        "max_concurrent_calls": 5,
        "max_retries": 3,
        "retry_backoff_minutes": "15,60,240"
    },
    {
        "id": "hosp-sjm",
        "name": "St. Jude Memorial Health",
        "code": "SJM",
        "timezone": "America/Chicago",
        "contact_email": "admin@sjm.health",
        "contact_phone": "312-555-0200",
        "permitted_call_start_hour": 9,
        "permitted_call_end_hour": 19,
        "max_concurrent_calls": 4,
        "max_retries": 3,
        "retry_backoff_minutes": "20,60,180"
    },
    {
        "id": "hosp-pcm",
        "name": "Pacific Coast Medical Center",
        "code": "PCM",
        "timezone": "America/Los_Angeles",
        "contact_email": "admin@pcm.health",
        "contact_phone": "415-555-0300",
        "permitted_call_start_hour": 8,
        "permitted_call_end_hour": 18,
        "max_concurrent_calls": 6,
        "max_retries": 4,
        "retry_backoff_minutes": "15,45,120"
    }
]

USERS_SEED = [
    {
        "id": "usr-plat-admin",
        "hospital_id": None,
        "username": "platform_admin",
        "full_name": "Dr. Eleanor Vance (Platform Director)",
        "email": "platform.admin@outreach.health",
        "role": UserRole.PLATFORM_ADMIN
    },
    {
        "id": "usr-hosp-admin-mgh",
        "hospital_id": "hosp-mgh",
        "username": "mgh_admin",
        "full_name": "Marcus Sterling (Hospital Operations Director)",
        "email": "marcus.sterling@mgh.health",
        "role": UserRole.HOSPITAL_ADMIN
    },
    {
        "id": "usr-camp-mgr-mgh",
        "hospital_id": "hosp-mgh",
        "username": "mgh_campaign_mgr",
        "full_name": "Rachel Adams (Outreach Campaign Lead)",
        "email": "rachel.adams@mgh.health",
        "role": UserRole.CAMPAIGN_MANAGER
    },
    {
        "id": "usr-clin-rev-mgh",
        "hospital_id": "hosp-mgh",
        "username": "mgh_clinical_rev",
        "full_name": "Sarah Lin, BSN, RN (Clinical Triage Navigator)",
        "email": "sarah.lin@mgh.health",
        "role": UserRole.CLINICAL_REVIEWER
    },
    {
        "id": "usr-hosp-admin-sjm",
        "hospital_id": "hosp-sjm",
        "username": "sjm_admin",
        "full_name": "Dr. Teresa Mendoza (Chief Medical Officer)",
        "email": "teresa.mendoza@sjm.health",
        "role": UserRole.HOSPITAL_ADMIN
    },
    {
        "id": "usr-camp-mgr-sjm",
        "hospital_id": "hosp-sjm",
        "username": "sjm_campaign_mgr",
        "full_name": "David Gallagher (Outreach Director)",
        "email": "david.gallagher@sjm.health",
        "role": UserRole.CAMPAIGN_MANAGER
    },
    {
        "id": "usr-clin-rev-sjm",
        "hospital_id": "hosp-sjm",
        "username": "sjm_clinical_rev",
        "full_name": "Elena Rostova, MSN, RN (Post-Acute Care Coordinator)",
        "email": "elena.rostova@sjm.health",
        "role": UserRole.CLINICAL_REVIEWER
    },
    {
        "id": "usr-hosp-admin-pcm",
        "hospital_id": "hosp-pcm",
        "username": "pcm_admin",
        "full_name": "Dr. Robert Vance, MD (VP Clinical Operations)",
        "email": "robert.vance@pcm.health",
        "role": UserRole.HOSPITAL_ADMIN
    },
    {
        "id": "usr-camp-mgr-pcm",
        "hospital_id": "hosp-pcm",
        "username": "pcm_campaign_mgr",
        "full_name": "Jessica Chen (Care Coordination Lead)",
        "email": "jessica.chen@pcm.health",
        "role": UserRole.CAMPAIGN_MANAGER
    },
    {
        "id": "usr-clin-rev-pcm",
        "hospital_id": "hosp-pcm",
        "username": "pcm_clinical_rev",
        "full_name": "Marcus Alvarez, BSN, RN (Triage Specialist)",
        "email": "marcus.alvarez@pcm.health",
        "role": UserRole.CLINICAL_REVIEWER
    }
]

async def seed_database(db: AsyncSession):
    """
    Seeds multi-tenant hospitals, RBAC users, clinical protocols, 250+ FHIR patients,
    and active post-discharge campaigns.
    """
    # Check if already seeded
    existing_hosp = (await db.execute(select(Hospital))).scalars().first()
    if existing_hosp:
        return

    # 1. Seed Hospitals
    hospitals_map = {}
    for h_data in HOSPITALS_SEED:
        h = Hospital(
            id=h_data["id"],
            name=h_data["name"],
            code=h_data["code"],
            timezone=h_data["timezone"],
            contact_email=h_data["contact_email"],
            contact_phone=h_data["contact_phone"],
            permitted_call_start_hour=h_data["permitted_call_start_hour"],
            permitted_call_end_hour=h_data["permitted_call_end_hour"],
            max_concurrent_calls=h_data["max_concurrent_calls"],
            max_retries=h_data["max_retries"],
            retry_backoff_minutes=h_data["retry_backoff_minutes"],
            status=HospitalStatus.READY_FOR_CAMPAIGNS
        )
        db.add(h)
        hospitals_map[h.id] = h
    await db.flush()

    # 2. Seed Users
    for u_data in USERS_SEED:
        u = User(
            id=u_data["id"],
            hospital_id=u_data["hospital_id"],
            username=u_data["username"],
            full_name=u_data["full_name"],
            email=u_data["email"],
            role=u_data["role"],
            is_active=True
        )
        db.add(u)
    await db.flush()

    # 3. Seed Protocols for each hospital
    for h_id in hospitals_map:
        for proto_tmpl in DEFAULT_PROTOCOLS:
            p_id = f"proto-{h_id}-{proto_tmpl['target_condition'].lower()}"
            p = ClinicalProtocol(
                id=p_id,
                hospital_id=h_id,
                code=f"{proto_tmpl['code']}-{h_id.upper()}",
                name=proto_tmpl["name"],
                target_condition=proto_tmpl["target_condition"],
                version=proto_tmpl["version"],
                description=proto_tmpl["description"],
                is_active=True
            )
            db.add(p)
            await db.flush()

            for rf in proto_tmpl["red_flags"]:
                db.add(ProtocolRedFlag(
                    id=f"rf-{uuid.uuid4().hex[:8]}",
                    protocol_id=p.id,
                    indicator=rf["indicator"],
                    severity=rf["severity"],
                    action_required=rf["action_required"],
                    citation=rf["citation"]
                ))

            for q in proto_tmpl["questions"]:
                db.add(ProtocolQuestion(
                    id=f"pq-{uuid.uuid4().hex[:8]}",
                    protocol_id=p.id,
                    sequence_order=q["sequence_order"],
                    category=q["category"],
                    question_text=q["question_text"],
                    expected_observation_key=q["expected_observation_key"],
                    guidance=q["guidance"]
                ))
    await db.flush()

    # 4. Create Active Campaigns for All Hospitals
    mgh_camp_chf = OutreachCampaign(
        id="camp-mgh-chf-01",
        hospital_id="hosp-mgh",
        name="MGH Congestive Heart Failure 48h Outreach",
        description="Priority post-discharge monitoring for CHF patients to reduce 30-day readmissions.",
        target_condition="CHF",
        status=CampaignStatus.RUNNING,
        followup_window_hours=48,
        priority_level=5,
        allocated_capacity=3
    )
    mgh_camp_ortho = OutreachCampaign(
        id="camp-mgh-ortho-02",
        hospital_id="hosp-mgh",
        name="MGH Joint Replacement Recovery Program",
        description="Outreach monitoring for post-TKA and hip arthroplasty surgical site safety.",
        target_condition="ORTHO",
        status=CampaignStatus.RUNNING,
        followup_window_hours=72,
        priority_level=4,
        allocated_capacity=2
    )

    sjm_camp_chf = OutreachCampaign(
        id="camp-sjm-chf-01",
        hospital_id="hosp-sjm",
        name="St. Jude Heart Failure Outreach",
        description="30-day post-acute congestive heart failure monitoring to prevent preventable cardiac readmissions.",
        target_condition="CHF",
        status=CampaignStatus.RUNNING,
        followup_window_hours=48,
        priority_level=5,
        allocated_capacity=2
    )
    sjm_camp_ortho = OutreachCampaign(
        id="camp-sjm-ortho-02",
        hospital_id="hosp-sjm",
        name="St. Jude Joint Replacement Recovery",
        description="Outreach monitoring for post-TKA and hip arthroplasty surgical site safety and mobility.",
        target_condition="ORTHO",
        status=CampaignStatus.RUNNING,
        followup_window_hours=72,
        priority_level=4,
        allocated_capacity=1
    )
    sjm_camp_sepsis = OutreachCampaign(
        id="camp-sjm-sepsis-03",
        hospital_id="hosp-sjm",
        name="St. Jude Post-Sepsis Care Transition",
        description="Intensive 48-hour post-discharge recovery monitoring for high-risk sepsis recovery patients.",
        target_condition="SEPSIS",
        status=CampaignStatus.RUNNING,
        followup_window_hours=48,
        priority_level=4,
        allocated_capacity=1
    )

    pcm_camp_chf = OutreachCampaign(
        id="camp-pcm-chf-01",
        hospital_id="hosp-pcm",
        name="PCM Cardiovascular Post-Acute Follow-Up",
        description="Comprehensive post-discharge cardiac protocol for fluid balance, weight log, and ACE-I adherence.",
        target_condition="CHF",
        status=CampaignStatus.RUNNING,
        followup_window_hours=48,
        priority_level=5,
        allocated_capacity=2
    )
    pcm_camp_ortho = OutreachCampaign(
        id="camp-pcm-ortho-02",
        hospital_id="hosp-pcm",
        name="PCM Orthopedic Joint Recovery Cohort",
        description="Post-operative monitoring for total knee and hip replacement recovery, wound inspection and mobility.",
        target_condition="ORTHO",
        status=CampaignStatus.RUNNING,
        followup_window_hours=72,
        priority_level=4,
        allocated_capacity=2
    )
    pcm_camp_sepsis = OutreachCampaign(
        id="camp-pcm-sepsis-03",
        hospital_id="hosp-pcm",
        name="PCM Post-Sepsis Care Transition",
        description="Post-sepsis surveillance monitoring for recurrent bacteremia, vital sign instability, and delirium.",
        target_condition="SEPSIS",
        status=CampaignStatus.RUNNING,
        followup_window_hours=48,
        priority_level=4,
        allocated_capacity=2
    )

    for c in [mgh_camp_chf, mgh_camp_ortho, sjm_camp_chf, sjm_camp_ortho, sjm_camp_sepsis, pcm_camp_chf, pcm_camp_ortho, pcm_camp_sepsis]:
        db.add(c)
    await db.flush()

    camps_map = {
        "hosp-mgh": {"CHF": mgh_camp_chf, "ORTHO": mgh_camp_ortho, "SEPSIS": mgh_camp_chf},
        "hosp-sjm": {"CHF": sjm_camp_chf, "ORTHO": sjm_camp_ortho, "SEPSIS": sjm_camp_sepsis},
        "hosp-pcm": {"CHF": pcm_camp_chf, "ORTHO": pcm_camp_ortho, "SEPSIS": pcm_camp_sepsis}
    }

    medications_by_condition = {
        "CHF": [
            ("Lisinopril", "10 mg", "Take 1 tablet by mouth daily in the morning"),
            ("Furosemide", "40 mg", "Take 1 tablet by mouth twice daily"),
            ("Metoprolol Succinate", "25 mg", "Take 1 tablet by mouth daily with food")
        ],
        "ORTHO": [
            ("Oxycodone-Acetaminophen", "5-325 mg", "Take 1 tablet by mouth every 6 hours as needed for severe pain"),
            ("Enoxaparin Sodium", "40 mg/0.4 mL", "Inject subcutaneously once daily for 14 days"),
            ("Cephalexin", "500 mg", "Take 1 capsule by mouth every 8 hours for 7 days")
        ],
        "SEPSIS": [
            ("Amoxicillin-Potassium Clavulanate", "875-125 mg", "Take 1 tablet by mouth every 12 hours with meal"),
            ("Prednisone", "10 mg", "Take 1 tablet by mouth daily with food"),
            ("Omeprazole", "20 mg", "Take 1 capsule by mouth daily before breakfast")
        ]
    }

    # 5. Generate 300 realistic patients across all three hospitals
    now = get_ist_now()
    eval_time = now.replace(hour=14, minute=0, second=0, microsecond=0)
    conditions_pool = [
        {"cond": "CHF", "code": "I50.9", "name": "Congestive Heart Failure", "window": 48},
        {"cond": "ORTHO", "code": "Z96.651", "name": "Total Knee Arthroplasty (TKA)", "window": 72},
        {"cond": "SEPSIS", "code": "A41.9", "name": "Sepsis recovery", "window": 48}
    ]

    random.seed(42) # Deterministic seed for reproducible evaluation
    for i in range(1, 301):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        if i <= 150:
            h_id = "hosp-mgh"
            hosp_idx = i
        elif i <= 225:
            h_id = "hosp-sjm"
            hosp_idx = i - 150
        else:
            h_id = "hosp-pcm"
            hosp_idx = i - 225

        hosp = hospitals_map[h_id]
        c_spec = conditions_pool[(i - 1) % len(conditions_pool)]
        risk_score = round(random.uniform(1.5, 9.5), 1)
        if risk_score >= 8.0:
            tier = RiskTier.CRITICAL
        elif risk_score >= 6.0:
            tier = RiskTier.HIGH
        elif risk_score >= 4.0:
            tier = RiskTier.MODERATE
        else:
            tier = RiskTier.LOW

        pat_id = f"pat-{h_id}-{hosp_idx:03d}"
        pat = Patient(
            id=pat_id,
            hospital_id=h_id,
            mrn=f"{hosp.code}-{100000 + hosp_idx}",
            first_name=first,
            last_name=last,
            date_of_birth=f"{random.randint(1945, 1990)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            gender="M" if random.random() > 0.5 else "F",
            phone_number=f"555-{random.randint(100,999):03d}-{random.randint(1000,9999):04d}",
            email=f"{first.lower()}.{last.lower()}@{h_id[5:]}-health.org",
            preferred_language="en",
            consent_for_outreach=True,
            baseline_risk_score=risk_score,
            risk_tier=tier
        )
        db.add(pat)
        await db.flush()

        # Discharge encounter: 1 to 46 hours ago
        discharge_hours_ago = random.uniform(1.0, 46.0)
        discharge_dt = now - timedelta(hours=discharge_hours_ago)
        admission_dt = discharge_dt - timedelta(days=random.randint(2, 6))

        enc = Encounter(
            id=f"enc-{pat.id}",
            hospital_id=h_id,
            patient_id=pat.id,
            encounter_type="inpatient",
            admission_date=admission_dt,
            discharge_date=discharge_dt,
            discharge_disposition="Home",
            attending_physician="Dr. Sarah Lin, MD" if h_id == "hosp-mgh" else ("Dr. Marcus Vance, MD" if h_id == "hosp-sjm" else "Dr. Elena Rostova, MD"),
            primary_diagnosis=c_spec["name"],
            discharge_summary=f"Patient admitted for acute management of {c_spec['name']}. Condition stabilized prior to home discharge."
        )
        db.add(enc)
        await db.flush()

        # Condition
        db.add(Condition(
            id=f"cond-{pat.id}",
            hospital_id=h_id,
            patient_id=pat.id,
            icd10_code=c_spec["code"],
            name=c_spec["name"],
            clinical_status="active"
        ))

        # Care Plan
        cutoff_dt = discharge_dt + timedelta(hours=c_spec["window"])
        db.add(CarePlan(
            id=f"cp-{pat.id}",
            hospital_id=h_id,
            patient_id=pat.id,
            encounter_id=enc.id,
            protocol_code=f"PROTO-{c_spec['cond']}",
            target_window_hours=c_spec["window"],
            instructions="Maintain daily weight log, report sudden dyspnea or wound changes immediately.",
            red_flag_warnings="Weight gain >= 3 lbs, chest pain, calf swelling, fever > 101F."
        ))

        # Medications
        med_specs = medications_by_condition.get(c_spec["cond"], medications_by_condition["CHF"])
        for m_name, m_dose, m_inst in med_specs:
            db.add(Medication(
                id=f"med-{uuid.uuid4().hex[:8]}",
                hospital_id=h_id,
                patient_id=pat.id,
                name=m_name,
                dosage=m_dose,
                instructions=m_inst,
                active=True
            ))
        await db.flush()

        # Outreach Task for patient in all hospitals
        target_camp = camps_map[h_id][c_spec["cond"]]
        # Status distribution:
        # 60% PENDING, 15% RETRY_SCHEDULED, 15% COMPLETED, 6% ESCALATED, 4% MANUAL_FOLLOW_UP
        if hosp_idx % 15 == 0:
            task_status = TaskStatus.ESCALATED
            attempts = 1
            retry_at = None
            fail_reason = "Clinical Red-Flag Encountered During Outreach Intake"
        elif hosp_idx % 7 == 0:
            task_status = TaskStatus.COMPLETED
            attempts = 1
            retry_at = None
            fail_reason = None
        elif hosp_idx % 6 == 0:
            task_status = TaskStatus.RETRY_SCHEDULED
            attempts = 1
            retry_at = now + timedelta(minutes=20)
            fail_reason = "Patient phone busy"
        elif hosp_idx % 23 == 0:
            task_status = TaskStatus.MANUAL_FOLLOW_UP
            attempts = hosp.max_retries
            retry_at = None
            fail_reason = "Exhausted maximum retry attempts - phone unreachable."
        else:
            task_status = TaskStatus.PENDING
            attempts = 0
            retry_at = None
            fail_reason = None

        task = OutreachTask(
            id=f"task-{h_id}-{hosp_idx:03d}",
            hospital_id=h_id,
            campaign_id=target_camp.id,
            patient_id=pat.id,
            encounter_id=enc.id,
            status=task_status,
            clinical_risk_score=risk_score,
            clinical_cutoff_time=cutoff_dt,
            max_retries=hosp.max_retries,
            attempts_count=attempts,
            last_attempt_at=now - timedelta(minutes=30) if attempts > 0 else None,
            next_retry_at=retry_at,
            last_failure_reason=fail_reason
        )
        task.priority_score = prioritizer.calculate_priority(task, target_camp, pat, hosp, eval_time)
        db.add(task)
        await db.flush()

        # For COMPLETED and ESCALATED tasks, seed CallRecord and CallTurn
        if task_status in (TaskStatus.COMPLETED, TaskStatus.ESCALATED):
            call_outcome = CallOutcome.SUCCESSFUL_COMPLETION if task_status == TaskStatus.COMPLETED else CallOutcome.ESCALATION_TRIGGERED
            call_id = f"call-{task.id}"
            call_start = now - timedelta(minutes=random.randint(15, 180))
            call_dur = random.randint(180, 360)
            call_end = call_start + timedelta(seconds=call_dur)

            call_rec = CallRecord(
                id=call_id,
                hospital_id=h_id,
                task_id=task.id,
                patient_id=pat.id,
                campaign_id=target_camp.id,
                attempt_number=task.attempts_count or 1,
                start_time=call_start,
                end_time=call_end,
                duration_seconds=call_dur,
                outcome=call_outcome,
                triage_classification=UrgencyLevel.URGENT if task_status == TaskStatus.ESCALATED else UrgencyLevel.ROUTINE,
                clinical_observations_json='{"symptoms_stable": true, "medication_confirmed": true}' if task_status == TaskStatus.COMPLETED else '{"acute_symptom": true, "safety_risk": "elevated"}',
                protocol_citations_json=f'["{target_camp.target_condition} Protocol v2.0"]',
                consensus_decision="AUTO_ESCALATE" if task_status == TaskStatus.ESCALATED else "NO_ACTION_NEEDED",
                consensus_disagreement=False,
                escalation_created=(task_status == TaskStatus.ESCALATED),
                documentation_summary=f"Automated outreach call for {pat.first_name} {pat.last_name} ({target_camp.name}). Patient condition assessed per approved protocol.",
                ehr_sync_status="SYNCED",
                ehr_sync_details='{"fhir_bundle_id": "bundle-sync-success"}',
                model_name="deterministic-healthcare-agent",
                prompt_tokens=450,
                completion_tokens=220,
                estimated_cost=0.0035,
                latency_ms=850
            )
            db.add(call_rec)
            await db.flush()

            db.add(CallTurn(
                id=f"turn-{call_id}-1",
                call_id=call_id,
                speaker="AGENT",
                text=f"Hello, this is AegisHealth calling on behalf of {hosp.name}. Am I speaking with {pat.first_name}?",
                turn_index=1,
                intent="greeting_identity_verification"
            ))
            db.add(CallTurn(
                id=f"turn-{call_id}-2",
                call_id=call_id,
                speaker="PATIENT",
                text=f"Yes, this is {pat.first_name}.",
                turn_index=2,
                intent="identity_confirmed"
            ))
            db.add(CallTurn(
                id=f"turn-{call_id}-3",
                call_id=call_id,
                speaker="AGENT",
                text=f"Thank you, {pat.first_name}. I'm following up on your recent discharge. Are you having any difficulty breathing, new pain, or fever?",
                turn_index=3,
                intent="symptom_screening"
            ))

            if task_status == TaskStatus.COMPLETED:
                db.add(CallTurn(
                    id=f"turn-{call_id}-4",
                    call_id=call_id,
                    speaker="PATIENT",
                    text="No, I am feeling much better and taking my medications as prescribed.",
                    turn_index=4,
                    intent="symptoms_negative"
                ))
                db.add(CallTurn(
                    id=f"turn-{call_id}-5",
                    call_id=call_id,
                    speaker="AGENT",
                    text="That is great news. Please continue taking your prescribed medications. If you have any concerns, do not hesitate to contact your care team.",
                    turn_index=5,
                    intent="wrapup_advice"
                ))
            else:
                db.add(CallTurn(
                    id=f"turn-{call_id}-4",
                    call_id=call_id,
                    speaker="PATIENT",
                    text="Actually, I've had sudden swelling in my legs, gained 4 pounds since yesterday, and I feel short of breath lying down.",
                    turn_index=4,
                    intent="acute_symptom_reported"
                ))
                db.add(CallTurn(
                    id=f"turn-{call_id}-5",
                    call_id=call_id,
                    speaker="AGENT",
                    text="Thank you for telling me. Based on your symptoms of rapid weight gain and shortness of breath, I am escalating this immediately to a clinical reviewer for urgent callback.",
                    turn_index=5,
                    intent="escalation_notified"
                ))

        # For ESCALATED tasks, seed Escalation record
        if task_status == TaskStatus.ESCALATED:
            esc = Escalation(
                id=f"esc-{task.id}",
                hospital_id=h_id,
                task_id=task.id,
                call_id=f"call-{task.id}",
                patient_id=pat.id,
                campaign_id=target_camp.id,
                status=EscalationStatus.OPEN,
                severity=UrgencyLevel.URGENT,
                trigger_reason=f"Acute symptom report: Sudden rapid weight gain and resting dyspnea ({c_spec['cond']})",
                clinical_indicators='["Sudden weight gain >= 3 lbs", "Resting orthopnea", "Peripheral edema"]',
                protocol_citations=f"[{c_spec['cond']} Post-Discharge Protocol §4.2: Red Flag Urgency]",
                consensus_rationale="Dual-LLM consensus: Both triage and safety critic flagged acute clinical decompensation.",
                assigned_reviewer_name=None,
                assigned_reviewer_id=None
            )
            db.add(esc)
            await db.flush()

            db.add(EscalationNote(
                id=f"note-{uuid.uuid4().hex[:8]}",
                escalation_id=esc.id,
                author_id="usr-system-ai",
                author_name="AegisHealth Safety Monitor",
                note_text="Automated clinical escalation initiated from outbound conversational triage."
            ))

    # 6. Seed Audit Logs for each hospital
    for hid in hospitals_map:
        db.add(AuditLog(
            id=f"audit-{uuid.uuid4().hex[:8]}",
            hospital_id=hid,
            actor_id=f"usr-hosp-admin-{hid[5:]}",
            actor_role="HOSPITAL_ADMIN",
            action="CONFIG_UPDATE",
            target_entity="Hospital",
            target_id=hid,
            details_json='{"event": "Outbound outreach campaigns initialized and verified"}'
        ))

    await db.commit()


