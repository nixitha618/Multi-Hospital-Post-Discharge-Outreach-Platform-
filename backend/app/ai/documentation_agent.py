import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from backend.app.schemas.ai import DocumentationOutput, StructuredTriageOutput, EscalationConsensusResult
from backend.app.models.patient import Patient
from backend.app.models.organization import Hospital
from backend.app.time_utils import get_ist_now

class DocumentationAgent:
    """
    Clinical Documentation Agent.
    Synthesizes conversational interactions, triage results, and consensus decisions
    into standard SOAP notes and FHIR records.
    """

    @staticmethod
    def generate_documentation(
        patient: Patient,
        hospital: Hospital,
        transcript: str,
        triage_output: StructuredTriageOutput,
        consensus_result: EscalationConsensusResult
    ) -> DocumentationOutput:
        now_str = get_ist_now().strftime("%Y-%m-%d %H:%M IST")
        
        indicators_str = ", ".join([f"{i.symptom_key} ({i.severity})" for i in triage_output.observed_indicators]) or "No acute symptoms reported"
        citations_str = ", ".join(triage_output.protocol_references)
        
        subjective = (
            f"Patient {patient.first_name} {patient.last_name} contacted via automated post-discharge outreach. "
            f"Patient dialogue: '{transcript[:150]}...'"
        )

        objective = (
            f"Structured Indicators: {indicators_str}. "
            f"Protocol Evaluated: {citations_str}."
        )

        assessment = (
            f"Triage Urgency: {triage_output.triage_classification.value}. "
            f"Consensus: {consensus_result.consensus_decision.value} (Agreement: {consensus_result.agreement}). "
            f"Clinical Reasoning: {triage_output.clinical_reasoning}"
        )

        if consensus_result.escalate_to_human:
            plan = (
                f"ACTION REQUIRED: Human clinical escalation initiated. Assigned to nursing triage queue. "
                f"Recommendations: {'; '.join(triage_output.suggested_nurse_actions)}."
            )
        else:
            plan = "Routine post-discharge recovery confirmed. Patient educated on red flags and follow-up care. Case closed."

        summary = (
            f"--- POST-DISCHARGE OUTREACH ENCOUNTER NOTE ---\n"
            f"Date/Time: {now_str}\n"
            f"Facility: {hospital.name}\n"
            f"Patient: {patient.first_name} {patient.last_name} (MRN: {patient.mrn})\n\n"
            f"S: {subjective}\n"
            f"O: {objective}\n"
            f"A: {assessment}\n"
            f"P: {plan}\n"
            f"---------------------------------------------"
        )

        return DocumentationOutput(
            summary=summary,
            chief_complaint="Post-discharge recovery follow-up",
            subjective_findings=subjective,
            objective_data=objective,
            assessment=assessment,
            plan_and_followup=plan,
            requires_callback=False
        )

documentation_agent = DocumentationAgent()
