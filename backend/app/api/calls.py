import uuid
import json
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from backend.app.database import get_db
from backend.app.time_utils import get_ist_now
from backend.app.api.deps import get_tenant_id, get_user_id
from backend.app.models.campaign import OutreachTask, OutreachCampaign
from backend.app.models.patient import Patient, Encounter
from backend.app.models.organization import Hospital
from backend.app.models.call import CallRecord, CallTurn
from backend.app.models.escalation import Escalation, EscalationNote
from backend.app.models.audit import AuditLog
from backend.app.models.enums import CallOutcome, TaskStatus, UrgencyLevel, EscalationStatus
from backend.app.schemas.call import CallRecordResponse, CallTurnResponse, CallInitiateRequest, InteractiveTurnRequest
from backend.app.ai.intake_agent import voice_intake_agent
from backend.app.ai.groq_service import groq_service
from backend.app.ai.triage_agent import clinical_triage_agent
from backend.app.ai.consensus_engine import consensus_engine
from backend.app.ai.documentation_agent import documentation_agent
from backend.app.protocols.store import protocol_store
from backend.app.ehr.mock_service import mock_ehr_service
from backend.app.ehr.fhir_models import FHIRCommunication
from backend.app.queue.concurrency import concurrency_governor

router = APIRouter(prefix="/calls", tags=["Calls & Live Dialogue"])

@router.get("", response_model=List[CallRecordResponse])
async def list_call_records(
    limit: int = 50,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(CallRecord)
        .where(CallRecord.hospital_id == tenant_id)
        .order_by(CallRecord.start_time.desc())
        .limit(limit)
        .options(selectinload(CallRecord.turns))
    )
    res = await db.execute(query)
    return list(res.scalars().all())

@router.get("/{call_id}", response_model=CallRecordResponse)
async def get_call_record(
    call_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(CallRecord)
        .where(CallRecord.id == call_id, CallRecord.hospital_id == tenant_id)
        .options(selectinload(CallRecord.turns))
    )
    call = (await db.execute(query)).scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call record not found")
    return call

@router.post("/start")
async def start_interactive_call(
    request: CallInitiateRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    # 1. Load task and verify slot reservation
    task_q = (
        select(OutreachTask)
        .where(OutreachTask.id == request.task_id, OutreachTask.hospital_id == tenant_id)
        .options(
            selectinload(OutreachTask.patient),
            selectinload(OutreachTask.campaign)
        )
    )
    task = (await db.execute(task_q)).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Outreach task not found")

    # Reserve concurrency slot if not already CALLING
    if task.status != TaskStatus.CALLING:
        success, msg = await concurrency_governor.reserve_call_slot(db, task.id, request.worker_id or "web-interactive")
        if not success:
            raise HTTPException(status_code=429, detail=f"Cannot initiate call: {msg}")

    # Load hospital, campaign, patient and protocol
    hosp = (await db.execute(select(Hospital).where(Hospital.id == tenant_id))).scalar_one()
    camp = (await db.execute(select(OutreachCampaign).where(OutreachCampaign.id == task.campaign_id))).scalar_one()
    pat = (await db.execute(select(Patient).where(Patient.id == task.patient_id))).scalar_one()
    protocol = await protocol_store.get_protocol_for_condition(db, tenant_id, camp.target_condition)

    # Create CallRecord
    call_id = f"call-{uuid.uuid4().hex[:8]}"
    now = get_ist_now()
    call = CallRecord(
        id=call_id,
        hospital_id=tenant_id,
        task_id=task.id,
        patient_id=pat.id,
        campaign_id=camp.id,
        attempt_number=task.attempts_count,
        start_time=now,
        duration_seconds=0,
        outcome=CallOutcome.SUCCESSFUL_COMPLETION, # In progress baseline
        ehr_sync_status="PENDING",
        model_name="Aegis-Clinical-Intake-v2.1"
    )
    db.add(call)

    # Generate Agent Opening Greeting (Turn 0)
    initial_turn_data = voice_intake_agent.generate_opening_turn(pat, hosp, protocol)
    turn = CallTurn(
        id=f"turn-{uuid.uuid4().hex[:8]}",
        call_id=call_id,
        speaker=initial_turn_data["speaker"],
        text=initial_turn_data["text"],
        turn_index=0,
        intent=initial_turn_data["intent"]
    )
    db.add(turn)
    await db.commit()

    return {
        "call_id": call_id,
        "task_id": task.id,
        "patient": {
            "name": f"{pat.first_name} {pat.last_name}",
            "mrn": pat.mrn,
            "risk_score": task.clinical_risk_score,
            "condition": camp.target_condition,
            "attempt_number": task.attempts_count,
            "max_retries": task.max_retries
        },
        "initial_turn": initial_turn_data
    }

@router.post("/turn")
async def handle_patient_speech_turn(
    request: InteractiveTurnRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(CallRecord)
        .where(CallRecord.id == request.call_id, CallRecord.hospital_id == tenant_id)
        .options(selectinload(CallRecord.turns))
    )
    call = (await db.execute(query)).scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call record not found")

    # Load patient, hospital, protocol
    pat = (await db.execute(select(Patient).where(Patient.id == call.patient_id))).scalar_one()
    hosp = (await db.execute(select(Hospital).where(Hospital.id == tenant_id))).scalar_one()
    camp = (await db.execute(select(OutreachCampaign).where(OutreachCampaign.id == call.campaign_id))).scalar_one()
    protocol = await protocol_store.get_protocol_for_condition(db, tenant_id, camp.target_condition)

    # 1. Record Patient Turn
    p_turn_idx = len(call.turns)
    patient_turn = CallTurn(
        id=f"turn-{uuid.uuid4().hex[:8]}",
        call_id=call.id,
        speaker="PATIENT",
        text=request.patient_speech,
        turn_index=p_turn_idx,
        intent="patient_response"
    )
    db.add(patient_turn)
    await db.flush()

    # Build dialogue history
    history = [{"speaker": t.speaker, "text": t.text} for t in sorted(call.turns, key=lambda x: x.turn_index)]

    # 2. Generate Agent Turn
    agent_reply = voice_intake_agent.process_patient_turn(
        patient=pat,
        hospital=hosp,
        protocol=protocol,
        dialogue_history=history,
        latest_patient_speech=request.patient_speech
    )

    agent_turn = CallTurn(
        id=f"turn-{uuid.uuid4().hex[:8]}",
        call_id=call.id,
        speaker="AGENT",
        text=agent_reply["text"],
        turn_index=p_turn_idx + 1,
        intent=agent_reply.get("intent", "reply")
    )
    db.add(agent_turn)
    await db.commit()

    return {
        "call_id": call.id,
        "patient_turn": {"speaker": "PATIENT", "text": request.patient_speech, "turn_index": p_turn_idx},
        "agent_turn": agent_reply,
        "action_directive": agent_reply.get("action", "CONTINUE")
    }

@router.post("/{call_id}/finish")
async def finish_call(
    call_id: str,
    simulated_outcome: Optional[CallOutcome] = None,
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(CallRecord)
        .where(CallRecord.id == call_id, CallRecord.hospital_id == tenant_id)
        .options(selectinload(CallRecord.turns))
    )
    call = (await db.execute(query)).scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call record not found")

    task = (await db.execute(select(OutreachTask).where(OutreachTask.id == call.task_id))).scalar_one()
    pat = (await db.execute(select(Patient).where(Patient.id == call.patient_id))).scalar_one()
    hosp = (await db.execute(select(Hospital).where(Hospital.id == tenant_id))).scalar_one()
    camp = (await db.execute(select(OutreachCampaign).where(OutreachCampaign.id == call.campaign_id))).scalar_one()

    # Assemble complete transcript
    transcript_lines = [f"{t.speaker}: {t.text}" for t in sorted(call.turns, key=lambda x: x.turn_index)]
    full_transcript = "\n".join(transcript_lines)
    call.raw_transcript = full_transcript
    call.end_time = get_ist_now()
    call.duration_seconds = max(15, int((call.end_time - call.start_time).total_seconds()))

    # Run Clinical Triage
    triage_output = clinical_triage_agent.evaluate_transcript(
        transcript=full_transcript,
        patient_name=f"{pat.first_name} {pat.last_name}",
        condition=camp.target_condition
    )
    call.triage_classification = triage_output.triage_classification
    call.clinical_observations_json = json.dumps([i.model_dump() for i in triage_output.observed_indicators])
    call.protocol_citations_json = json.dumps(triage_output.protocol_references)

    # Run Escalation Consensus
    consensus_result = consensus_engine.evaluate_consensus(
        triage_output=triage_output,
        transcript=full_transcript,
        patient_risk_tier=pat.risk_tier.value
    )
    call.consensus_decision = consensus_result.consensus_decision.value
    call.consensus_disagreement = consensus_result.disagreement_detected
    call.consensus_details_json = json.dumps(consensus_result.model_dump())

    # Determine final outcome and task state
    if simulated_outcome:
        call.outcome = simulated_outcome
        if simulated_outcome == CallOutcome.SUCCESSFUL_COMPLETION:
            call.triage_classification = UrgencyLevel.ROUTINE
            call.consensus_decision = UrgencyLevel.ROUTINE.value
            call.escalation_created = False
            consensus_result.consensus_decision = UrgencyLevel.ROUTINE
            consensus_result.escalate_to_human = False
            triage_output.triage_classification = UrgencyLevel.ROUTINE
            triage_output.escalation_recommended = False
            triage_output.clinical_reasoning = "Patient confirmed stable normal recovery without acute red flags."
        elif simulated_outcome == CallOutcome.ESCALATION_TRIGGERED:
            call.triage_classification = UrgencyLevel.URGENT
            call.consensus_decision = UrgencyLevel.URGENT.value
            call.escalation_created = True
            consensus_result.consensus_decision = UrgencyLevel.URGENT
            consensus_result.escalate_to_human = True
            triage_output.triage_classification = UrgencyLevel.URGENT
            triage_output.escalation_recommended = True
    elif consensus_result.escalate_to_human:
        call.outcome = CallOutcome.ESCALATION_TRIGGERED
    else:
        call.outcome = CallOutcome.SUCCESSFUL_COMPLETION

    # Generate Clinical Documentation matching the validated outcome
    doc_output = documentation_agent.generate_documentation(
        patient=pat,
        hospital=hosp,
        transcript=full_transcript,
        triage_output=triage_output,
        consensus_result=consensus_result
    )
    call.documentation_summary = doc_output.summary

    if call.outcome == CallOutcome.ESCALATION_TRIGGERED:
        esc_sev = consensus_result.consensus_decision
        if esc_sev == UrgencyLevel.ROUTINE:
            esc_sev = UrgencyLevel.URGENT

        existing_escs = (await db.execute(
            select(Escalation).where(Escalation.task_id == task.id).order_by(Escalation.created_at.desc())
        )).scalars().all()

        if not existing_escs:
            esc_id = f"esc-{uuid.uuid4().hex[:8]}"
            esc = Escalation(
                id=esc_id,
                hospital_id=tenant_id,
                task_id=task.id,
                call_id=call.id,
                patient_id=pat.id,
                campaign_id=camp.id,
                severity=esc_sev,
                status=EscalationStatus.OPEN,
                trigger_reason=f"Clinical Triage ({esc_sev.value if hasattr(esc_sev, 'value') else esc_sev})",
                clinical_indicators=json.dumps([i.model_dump() for i in triage_output.observed_indicators]),
                protocol_citations=json.dumps(triage_output.protocol_references),
                consensus_rationale=consensus_result.final_rationale
            )
            db.add(esc)
        else:
            esc = existing_escs[0]
            esc.status = EscalationStatus.OPEN
            esc.call_id = call.id
            esc.severity = esc_sev
            esc.trigger_reason = f"Clinical Triage ({esc_sev.value if hasattr(esc_sev, 'value') else esc_sev})"
            esc.clinical_indicators = json.dumps([i.model_dump() for i in triage_output.observed_indicators])
            esc.protocol_citations = json.dumps(triage_output.protocol_references)
            esc.consensus_rationale = consensus_result.final_rationale
            if len(existing_escs) > 1:
                for dup in existing_escs[1:]:
                    await db.execute(delete(EscalationNote).where(EscalationNote.escalation_id == dup.id))
                    await db.delete(dup)

        call.escalation_created = True
        task.status = TaskStatus.ESCALATED
        task.attempts_count = min(task.attempts_count, task.max_retries)
    else:
        call.escalation_created = False
        task.status = TaskStatus.COMPLETED
        task.attempts_count = min(max(1, call.attempt_number or task.attempts_count), task.max_retries)
        # Patient ended up with normal recovery -> REMOVE patient from escalated box!
        prior_escs = (await db.execute(
            select(Escalation).where(
                (Escalation.task_id == task.id) | (Escalation.patient_id == task.patient_id)
            )
        )).scalars().all()
        for pe in prior_escs:
            await db.execute(delete(EscalationNote).where(EscalationNote.escalation_id == pe.id))
            await db.delete(pe)

    # Commit documentation to Mock EHR
    try:
        fhir_comm = FHIRCommunication(
            id=f"ehr-comm-{call.id}",
            subject_reference=f"Patient/{pat.id}",
            topic="Post-Discharge Outreach Encounter",
            payload_content=doc_output.summary,
            recipient_reference=f"Patient/{pat.id}",
            sender_reference=f"Organization/{tenant_id}"
        )
        ehr_res = await mock_ehr_service.post_communication(tenant_id, fhir_comm)
        call.ehr_sync_status = "SYNCED"
        call.ehr_sync_details = json.dumps(ehr_res)
    except Exception as e:
        call.ehr_sync_status = "FAILED"
        call.ehr_sync_details = str(e)

    # Release concurrency slot
    task.assigned_worker_id = None
    task.call_started_at = None
    task.last_heartbeat_at = None
    task.last_attempt_at = get_ist_now()

    # Audit log
    db.add(AuditLog(
        id=f"audit-{uuid.uuid4().hex[:10]}",
        hospital_id=tenant_id,
        actor_id=user_id,
        actor_role="SYSTEM",
        action=f"CALL_FINISHED_{call.outcome.value}",
        target_entity="CallRecord",
        target_id=call.id,
        details_json=json.dumps({
            "duration": call.duration_seconds,
            "escalated": call.escalation_created,
            "ehr_status": call.ehr_sync_status
        })
    ))

    await db.commit()
    await db.refresh(call)

    # Run LLM Dialogue Quality Evaluation
    dialogue_eval = groq_service.evaluate_dialogue_with_llm(
        transcript=full_transcript,
        patient_context={
            "patient_name": f"{pat.first_name} {pat.last_name}",
            "condition": camp.target_condition,
            "attempt": call.attempt_number
        },
        triage_summary={
            "classification": call.triage_classification.value,
            "consensus": call.consensus_decision
        }
    )

    return {
        "call_id": call.id,
        "outcome": call.outcome.value,
        "attempt_number": min(max(1, call.attempt_number), task.max_retries),
        "triage_urgency": call.triage_classification.value,
        "consensus": call.consensus_decision,
        "escalation_created": call.escalation_created,
        "ehr_sync_status": call.ehr_sync_status,
        "documentation_summary": call.documentation_summary,
        "dialogue_evaluation": dialogue_eval.model_dump()
    }

@router.post("/task/{task_id}/finish")
async def finish_call_by_task(
    task_id: str,
    simulated_outcome: Optional[CallOutcome] = None,
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    # Find most recent call for this task
    q = (
        select(CallRecord)
        .where(CallRecord.task_id == task_id, CallRecord.hospital_id == tenant_id)
        .order_by(CallRecord.start_time.desc())
        .limit(1)
    )
    call = (await db.execute(q)).scalar_one_or_none()
    if call:
        return await finish_call(call.id, simulated_outcome, tenant_id, user_id, db)

    # If call record wasn't created yet but task is CALLING, finish task directly
    task_q = select(OutreachTask).where(OutreachTask.id == task_id, OutreachTask.hospital_id == tenant_id)
    task = (await db.execute(task_q)).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    is_escalation = simulated_outcome == CallOutcome.ESCALATION_TRIGGERED
    task.status = TaskStatus.ESCALATED if is_escalation else TaskStatus.COMPLETED
    task.assigned_worker_id = None
    task.call_started_at = None
    task.last_heartbeat_at = None
    task.last_attempt_at = get_ist_now()

    if is_escalation:
        task.status = TaskStatus.ESCALATED
        task.attempts_count = min(task.attempts_count, task.max_retries)
        existing_escs = (await db.execute(
            select(Escalation).where(Escalation.task_id == task.id).order_by(Escalation.created_at.desc())
        )).scalars().all()

        if not existing_escs:
            esc_id = f"esc-{uuid.uuid4().hex[:8]}"
            esc = Escalation(
                id=esc_id,
                hospital_id=tenant_id,
                task_id=task.id,
                call_id=None,
                patient_id=task.patient_id,
                campaign_id=task.campaign_id,
                severity=UrgencyLevel.URGENT,
                status=EscalationStatus.OPEN,
                trigger_reason="Clinical Triage Escalation (Manual Operator Override)",
                clinical_indicators=json.dumps([{"type": "SYMPTOM", "value": "Acute clinical red flag reported by patient"}]),
                protocol_citations=json.dumps(["PROTO-RED-FLAG-OVERRIDE"]),
                consensus_rationale="Urgent human reviewer escalation requested via clinical operations control board."
            )
            db.add(esc)
        else:
            esc = existing_escs[0]
            esc.status = EscalationStatus.OPEN
            esc.severity = UrgencyLevel.URGENT
            esc.trigger_reason = "Clinical Triage Escalation (Manual Operator Override)"
            if len(existing_escs) > 1:
                for dup in existing_escs[1:]:
                    await db.execute(delete(EscalationNote).where(EscalationNote.escalation_id == dup.id))
                    await db.delete(dup)
    else:
        task.status = TaskStatus.COMPLETED
        task.attempts_count = min(max(1, task.attempts_count), task.max_retries)
        # Patient ended up with normal recovery -> REMOVE patient from escalated box!
        prior_escs = (await db.execute(
            select(Escalation).where(
                (Escalation.task_id == task_id) | (Escalation.patient_id == task.patient_id)
            )
        )).scalars().all()
        for pe in prior_escs:
            await db.execute(delete(EscalationNote).where(EscalationNote.escalation_id == pe.id))
            await db.delete(pe)

    await db.commit()
    return {
        "status": "success",
        "task_id": task_id,
        "new_status": task.status.value,
        "escalation_created": is_escalation
    }
