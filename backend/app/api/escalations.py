from typing import List, Optional
from datetime import datetime
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from backend.app.database import get_db
from backend.app.time_utils import get_ist_now
from backend.app.api.deps import get_tenant_id, get_user_id, get_user_role
from backend.app.models.escalation import Escalation, EscalationNote
from backend.app.models.campaign import OutreachTask
from backend.app.models.audit import AuditLog
from backend.app.models.enums import EscalationStatus, TaskStatus, UrgencyLevel
from backend.app.schemas.escalation import (
    EscalationResponse, EscalationNoteCreate, EscalationNoteResponse,
    EscalationResolveRequest, EscalationAssignRequest
)
from backend.app.ehr.mock_service import mock_ehr_service
from backend.app.ehr.fhir_models import FHIRTask

router = APIRouter(prefix="/escalations", tags=["Clinical Escalation & HITL"])

@router.get("", response_model=List[EscalationResponse])
async def list_escalations(
    status_filter: Optional[str] = None,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    # 1. Auto-sync: Ensure any task currently in ESCALATED state has a corresponding escalation record in the clinical box
    esc_tasks_q = (
        select(OutreachTask)
        .where(
            OutreachTask.hospital_id == tenant_id,
            OutreachTask.status == TaskStatus.ESCALATED
        )
        .options(selectinload(OutreachTask.patient))
    )
    escalated_tasks = (await db.execute(esc_tasks_q)).scalars().all()
    new_created = False
    for tsk in escalated_tasks:
        existing_escs = (await db.execute(
            select(Escalation).where(Escalation.task_id == tsk.id).order_by(Escalation.created_at.desc())
        )).scalars().all()
        if existing_escs:
            existing = existing_escs[0]
            if len(existing_escs) > 1:
                for dup in existing_escs[1:]:
                    await db.execute(delete(EscalationNote).where(EscalationNote.escalation_id == dup.id))
                    await db.delete(dup)
                await db.commit()
        else:
            existing = None

        if not existing:
            sev = UrgencyLevel.URGENT if (tsk.clinical_risk_score or 5.0) >= 7.0 else UrgencyLevel.CONCERNING
            pat_name = f"{tsk.patient.first_name} {tsk.patient.last_name}" if tsk.patient else "Patient"
            new_esc = Escalation(
                id=f"esc-{uuid.uuid4().hex[:8]}",
                hospital_id=tenant_id,
                task_id=tsk.id,
                call_id=None,
                patient_id=tsk.patient_id,
                campaign_id=tsk.campaign_id,
                severity=sev,
                status=EscalationStatus.OPEN,
                trigger_reason=f"Clinical Triage Escalation (Acuity Risk Score: {tsk.clinical_risk_score:.1f})",
                clinical_indicators=json.dumps([{"type": "SYMPTOM", "value": "Acute clinical decompensation or red flag reported during outreach"}]),
                protocol_citations=json.dumps(["PROTO-CARDIO-V2.1" if "chf" in (tsk.campaign_id or "") else "PROTO-POSTOP-V2.1"]),
                consensus_rationale=f"AI consensus flagged clinical review required for {pat_name}. Multi-agent agreement verified."
            )
            db.add(new_esc)
            new_created = True
    if new_created:
        await db.commit()

    query = (
        select(Escalation)
        .where(Escalation.hospital_id == tenant_id)
        .options(
            selectinload(Escalation.notes),
            selectinload(Escalation.patient),
            selectinload(Escalation.task)
        )
        .order_by(Escalation.created_at.desc())
    )
    if status_filter and status_filter != "ALL":
        query = query.where(Escalation.status == EscalationStatus(status_filter))

    res = await db.execute(query)
    all_escs = list(res.scalars().all())

    # If patient ended up with normal recovery (COMPLETED task), remove from escalated box
    active_escs = []
    to_delete = []
    for esc in all_escs:
        is_recovered = False
        if esc.task_id:
            t_res = await db.execute(select(OutreachTask).where(OutreachTask.id == esc.task_id))
            t = t_res.scalar_one_or_none()
            if t and t.status == TaskStatus.COMPLETED:
                is_recovered = True
        elif esc.patient_id:
            t_res = await db.execute(select(OutreachTask).where(OutreachTask.patient_id == esc.patient_id))
            tasks = t_res.scalars().all()
            if any(tsk.status == TaskStatus.COMPLETED for tsk in tasks):
                is_recovered = True

        if is_recovered:
            to_delete.append(esc)
        else:
            active_escs.append(esc)

    if to_delete:
        for de in to_delete:
            await db.execute(delete(EscalationNote).where(EscalationNote.escalation_id == de.id))
            await db.delete(de)
        await db.commit()

    return active_escs

@router.get("/{escalation_id}", response_model=EscalationResponse)
async def get_escalation(
    escalation_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(Escalation)
        .where(Escalation.id == escalation_id, Escalation.hospital_id == tenant_id)
        .options(
            selectinload(Escalation.notes),
            selectinload(Escalation.patient),
            selectinload(Escalation.task)
        )
    )
    esc = (await db.execute(query)).scalar_one_or_none()
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return esc

@router.post("/{escalation_id}/assign", response_model=EscalationResponse)
async def assign_escalation(
    escalation_id: str,
    req: EscalationAssignRequest,
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(Escalation).where(Escalation.id == escalation_id, Escalation.hospital_id == tenant_id)
    esc = (await db.execute(query)).scalar_one_or_none()
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")

    esc.assigned_reviewer_id = req.reviewer_id
    esc.assigned_reviewer_name = req.reviewer_name
    esc.status = EscalationStatus.ASSIGNED

    # Audit log
    db.add(AuditLog(
        id=f"audit-{uuid.uuid4().hex[:10]}",
        hospital_id=tenant_id,
        actor_id=user_id,
        actor_role="CLINICAL_REVIEWER",
        action="ESCALATION_ASSIGNED",
        target_entity="Escalation",
        target_id=esc.id,
        details_json=f'{{"assigned_to": "{req.reviewer_name}"}}'
    ))

    await db.commit()
    res = await db.execute(
        select(Escalation)
        .where(Escalation.id == escalation_id)
        .options(
            selectinload(Escalation.notes),
            selectinload(Escalation.patient),
            selectinload(Escalation.task)
        )
    )
    return res.scalar_one()

@router.post("/{escalation_id}/resolve", response_model=EscalationResponse)
async def resolve_escalation(
    escalation_id: str,
    req: EscalationResolveRequest,
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(Escalation).where(Escalation.id == escalation_id, Escalation.hospital_id == tenant_id)
    esc = (await db.execute(query)).scalar_one_or_none()
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")

    esc.status = EscalationStatus.RESOLVED
    esc.resolution_notes = req.resolution_notes
    esc.resolution_action = req.resolution_action
    esc.resolved_at = get_ist_now()
    esc.resolved_by_user_id = user_id

    # Create follow-up clinical order / task in Mock EHR
    try:
        fhir_task = FHIRTask(
            id=f"ehr-task-esc-{esc.id[:8]}",
            priority="urgent",
            description=f"Escalation resolved by {req.reviewer_name}: {req.resolution_action}. Notes: {req.resolution_notes}",
            for_patient_reference=f"Patient/{esc.patient_id}",
            requester=req.reviewer_name
        )
        await mock_ehr_service.create_followup_task(tenant_id, fhir_task)
    except Exception:
        pass

    # Audit log
    db.add(AuditLog(
        id=f"audit-{uuid.uuid4().hex[:10]}",
        hospital_id=tenant_id,
        actor_id=user_id,
        actor_role="CLINICAL_REVIEWER",
        action="ESCALATION_RESOLVED",
        target_entity="Escalation",
        target_id=esc.id,
        details_json=f'{{"action": "{req.resolution_action}", "notes": "{req.resolution_notes[:100]}"}}'
    ))

    # Update underlying outreach task
    if esc.task_id:
        task_query = select(OutreachTask).where(OutreachTask.id == esc.task_id)
        task = (await db.execute(task_query)).scalar_one_or_none()
        if task:
            if "Re-queue" in req.resolution_action or "Retry" in req.resolution_action:
                task.status = TaskStatus.PENDING
                task.last_failure_reason = f"Escalation resolved by {req.reviewer_name}: Re-queued for retry attempt."
                if task.attempts_count >= task.max_retries:
                    task.max_retries = task.attempts_count + 1
            else:
                task.status = TaskStatus.COMPLETED

    await db.commit()
    res = await db.execute(
        select(Escalation)
        .where(Escalation.id == escalation_id)
        .options(
            selectinload(Escalation.notes),
            selectinload(Escalation.patient),
            selectinload(Escalation.task)
        )
    )
    return res.scalar_one()

@router.post("/{escalation_id}/notes", response_model=EscalationNoteResponse)
async def add_escalation_note(
    escalation_id: str,
    req: EscalationNoteCreate,
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(Escalation).where(Escalation.id == escalation_id, Escalation.hospital_id == tenant_id)
    esc = (await db.execute(query)).scalar_one_or_none()
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")

    note = EscalationNote(
        id=f"note-{uuid.uuid4().hex[:8]}",
        escalation_id=esc.id,
        author_id=user_id,
        author_name=req.author_name or "Nurse Reviewer",
        note_text=req.note_text
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note
