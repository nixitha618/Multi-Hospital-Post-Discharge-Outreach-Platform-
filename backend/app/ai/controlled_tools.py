import uuid
import json
from datetime import datetime
from typing import Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.models.patient import Patient, Encounter
from backend.app.models.protocol import ClinicalProtocol
from backend.app.models.campaign import OutreachTask
from backend.app.models.escalation import Escalation
from backend.app.models.audit import AuditLog
from backend.app.models.enums import UrgencyLevel, TaskStatus
from backend.app.schemas.ai import ControlledToolRequest, ControlledToolResponse
from backend.app.ehr.mock_service import mock_ehr_service
from backend.app.ehr.fhir_models import FHIRCommunication, FHIRObservation, FHIRCodeableConcept, FHIRCoding
from backend.app.time_utils import get_ist_now

class ControlledToolBus:
    """
    Controlled AI Tool Bus.
    Enforces pattern:
    AI Request -> Tenant Authorization -> Schema Validation -> Business Rules -> Execution -> Audit Log -> Result.
    AI agents NEVER touch the database directly!
    """

    @staticmethod
    async def execute_tool(
        db: AsyncSession,
        hospital_id: str,
        request: ControlledToolRequest
    ) -> ControlledToolResponse:
        tool_name = request.tool_name
        args = request.arguments
        caller = request.caller_agent

        try:
            result_data = None

            # Tool 1: patient_lookup
            if tool_name == "patient_lookup":
                pat_id = args.get("patient_id")
                if not pat_id:
                    raise ValueError("Missing patient_id")
                # Tenant boundary enforcement: query strictly matches hospital_id
                q = select(Patient).where(Patient.id == pat_id, Patient.hospital_id == hospital_id)
                pat = (await db.execute(q)).scalar_one_or_none()
                if not pat:
                    raise PermissionError(f"Patient {pat_id} not found in tenant {hospital_id}")
                result_data = {
                    "patient_id": pat.id,
                    "name": f"{pat.first_name} {pat.last_name}",
                    "mrn": pat.mrn,
                    "risk_tier": pat.risk_tier.value,
                    "language": pat.preferred_language,
                    "phone": pat.phone_number
                }

            # Tool 2: encounter_lookup
            elif tool_name == "encounter_lookup":
                enc_id = args.get("encounter_id")
                q = select(Encounter).where(Encounter.id == enc_id, Encounter.hospital_id == hospital_id)
                enc = (await db.execute(q)).scalar_one_or_none()
                if not enc:
                    raise PermissionError(f"Encounter {enc_id} not found in tenant {hospital_id}")
                result_data = {
                    "encounter_id": enc.id,
                    "diagnosis": enc.primary_diagnosis,
                    "discharge_date": enc.discharge_date.isoformat(),
                    "attending_physician": enc.attending_physician,
                    "discharge_summary": enc.discharge_summary
                }

            # Tool 3: protocol_search
            elif tool_name == "protocol_search":
                cond = args.get("condition", "CHF")
                q = (
                    select(ClinicalProtocol)
                    .where(ClinicalProtocol.hospital_id == hospital_id, ClinicalProtocol.is_active == True)
                )
                protocols = list((await db.execute(q)).scalars().all())
                matched = [p for p in protocols if cond.upper() in p.target_condition.upper()]
                proto = matched[0] if matched else (protocols[0] if protocols else None)
                if proto:
                    result_data = {
                        "protocol_code": proto.code,
                        "name": proto.name,
                        "description": proto.description
                    }
                else:
                    result_data = {"protocol_code": "DEFAULT", "name": "Standard Post-Op Outreach"}

            # Tool 4: escalation_creation
            elif tool_name == "escalation_creation":
                task_id = args.get("task_id")
                patient_id = args.get("patient_id")
                severity_str = args.get("severity", "URGENT")
                trigger = args.get("trigger_reason", "Clinical escalation requested by AI")
                indicators = args.get("clinical_indicators", "")
                citations = args.get("protocol_citations", "")
                rationale = args.get("consensus_rationale", "")

                # Verify task belongs to this hospital
                task_q = select(OutreachTask).where(OutreachTask.id == task_id, OutreachTask.hospital_id == hospital_id)
                task = (await db.execute(task_q)).scalar_one_or_none()
                if not task:
                    raise PermissionError("Task unauthorized or does not belong to hospital tenant")

                esc_id = f"esc-{uuid.uuid4().hex[:8]}"
                sev = UrgencyLevel.URGENT if severity_str == "URGENT" else UrgencyLevel.CONCERNING
                esc = Escalation(
                    id=esc_id,
                    hospital_id=hospital_id,
                    task_id=task_id,
                    patient_id=patient_id,
                    campaign_id=task.campaign_id,
                    severity=sev,
                    trigger_reason=trigger,
                    clinical_indicators=indicators,
                    protocol_citations=citations,
                    consensus_rationale=rationale
                )
                db.add(esc)
                task.status = TaskStatus.ESCALATED
                await db.commit()
                result_data = {"escalation_id": esc_id, "status": "OPEN", "severity": sev.value}

            # Tool 5: callback_scheduling
            elif tool_name == "callback_scheduling":
                task_id = args.get("task_id")
                cb_time_str = args.get("callback_time")
                task_q = select(OutreachTask).where(OutreachTask.id == task_id, OutreachTask.hospital_id == hospital_id)
                task = (await db.execute(task_q)).scalar_one_or_none()
                if not task:
                    raise PermissionError("Task unauthorized")
                
                task.status = TaskStatus.CALLBACK_SCHEDULED
                task.callback_requested_time = datetime.fromisoformat(cb_time_str) if cb_time_str else get_ist_now()
                await db.commit()
                result_data = {"task_id": task_id, "status": "CALLBACK_SCHEDULED", "scheduled_for": task.callback_requested_time.isoformat()}

            # Tool 6: mock_ehr_update
            elif tool_name == "mock_ehr_update":
                patient_id = args.get("patient_id")
                summary_text = args.get("summary", "Outreach conducted")
                comm = FHIRCommunication(
                    id=f"comm-{uuid.uuid4().hex[:8]}",
                    subject_reference=f"Patient/{patient_id}",
                    topic="Post-Discharge Outreach",
                    payload_content=summary_text,
                    recipient_reference=f"Patient/{patient_id}",
                    sender_reference=f"Organization/{hospital_id}"
                )
                ehr_res = await mock_ehr_service.post_communication(hospital_id, comm)
                result_data = ehr_res

            else:
                raise ValueError(f"Unsupported tool: {tool_name}")

            # Create immutable audit record of the controlled tool execution
            audit_id = f"audit-tool-{uuid.uuid4().hex[:10]}"
            audit = AuditLog(
                id=audit_id,
                hospital_id=hospital_id,
                actor_id=caller,
                actor_role="AI_AGENT",
                action=f"CONTROLLED_TOOL_{tool_name.upper()}",
                target_entity="ToolBus",
                target_id=tool_name,
                details_json=json.dumps({"arguments": args, "result": result_data})
            )
            db.add(audit)
            await db.commit()

            return ControlledToolResponse(
                tool_name=tool_name,
                success=True,
                result=result_data,
                audit_id=audit_id
            )

        except Exception as e:
            return ControlledToolResponse(
                tool_name=tool_name,
                success=False,
                error_message=str(e)
            )

controlled_tool_bus = ControlledToolBus()
