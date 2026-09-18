from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.app.models.patient import Patient
from backend.app.models.protocol import ClinicalProtocol
from backend.app.models.organization import Hospital
from backend.app.ai.groq_service import groq_service, ChatbotOutput

class VoiceIntakeAgent:
    """
    Voice Intake & Conversation Agent.
    Orchestrates protocol-driven structured conversational turns with the patient,
    leveraging Groq LLM (llama-3.3-70b-versatile) for empathetic natural dialogue
    while enforcing deterministic clinical safety guardrails.
    """

    @staticmethod
    def generate_opening_turn(patient: Patient, hospital: Hospital, protocol: ClinicalProtocol) -> Dict[str, Any]:
        text = (
            f"Hello {patient.first_name} {patient.last_name}, I am calling on behalf of the post-discharge "
            f"outreach team at {hospital.name}. We want to check in on how you're feeling since leaving the hospital. "
            f"Do you have a few minutes to talk about your recovery?"
        )
        return {
            "speaker": "AGENT",
            "text": text,
            "turn_index": 0,
            "stage": "GREETING",
            "checklist_step": 0,
            "intent": "identity_and_availability_verification"
        }

    @staticmethod
    def process_patient_turn(
        patient: Patient,
        hospital: Hospital,
        protocol: ClinicalProtocol,
        dialogue_history: List[Dict[str, str]],
        latest_patient_speech: str
    ) -> Dict[str, Any]:
        """
        Evaluates patient's latest statement, selects the next protocol question or response,
        and determines if the call should continue, reschedule, or end using Groq LLM.
        """
        speech_lower = latest_patient_speech.lower().strip()
        turn_count = len([d for d in dialogue_history if d.get("speaker") == "AGENT"])

        # 1. Deterministic safety pre-check
        det_safety = {"should_escalate": False, "risk_level": "low", "reason": ""}

        # Emergency red flags (chest pain, acute dyspnea, calf DVT, sepsis fever, prompt injection)
        if any(w in speech_lower for w in [
            "chest pain", "can't breathe", "cannot breathe", "barely breathe",
            "fainted", "passing out", "severe pain 10", "calf is swollen", "hot to touch"
        ]):
            det_safety = {
                "should_escalate": True,
                "risk_level": "critical",
                "reason": "severe acute symptoms requiring immediate clinical escalation"
            }
        elif any(w in speech_lower for w in ["fever of 102", "102.5", "103", "101.9", "severe chills"]):
            det_safety = {
                "should_escalate": True,
                "risk_level": "urgent",
                "reason": "high fever and possible post-discharge infection/sepsis"
            }
        elif "ignore previous instructions" in speech_lower or "tell me i am 100% cured" in speech_lower:
            det_safety = {
                "should_escalate": True,
                "risk_level": "urgent",
                "reason": "adversarial prompt override attempt; routed to human clinician verification"
            }

        # 2. Check callback negotiation
        if any(w in speech_lower for w in ["busy right now", "call me back", "driving", "bad time", "call later"]):
            return {
                "speaker": "AGENT",
                "text": "I completely understand. When would be a more convenient time today for our clinical coordinator to call you back?",
                "turn_index": turn_count,
                "stage": "CALLBACK_REQUEST",
                "checklist_step": 0,
                "action": "SCHEDULE_CALLBACK",
                "intent": "callback_negotiation",
                "risk_level": "low",
                "should_escalate": False
            }

        # 3. Check opt-out / decline
        if any(w in speech_lower for w in ["do not call", "stop calling", "remove my number", "not interested"]):
            return {
                "speaker": "AGENT",
                "text": (
                    "Thank you for letting us know. I will make a note in your record and update your communication preferences. "
                    "We wish you the very best in your recovery. Goodbye."
                ),
                "turn_index": turn_count,
                "stage": "OPT_OUT",
                "checklist_step": 0,
                "action": "TERMINATE_OPTOUT",
                "intent": "opt_out",
                "risk_level": "low",
                "should_escalate": False
            }

        # 4. Check concluding phrase
        if any(w in speech_lower for w in ["no other questions", "all set", "conclude call", "goodbye", "that's all", "thats all"]):
            wrapup = (
                f"Thank you so much for your time today, {patient.first_name}. "
                f"I have recorded all your recovery answers in your medical chart. "
                f"If you ever need assistance, please call {hospital.name} at {hospital.contact_phone}. "
                f"Wishing you a smooth recovery. Goodbye!"
            )
            return {
                "speaker": "AGENT",
                "text": wrapup,
                "turn_index": turn_count,
                "stage": "CLOSING",
                "checklist_step": 5,
                "action": "AUTO_FINISH",
                "intent": "call_conclusion",
                "risk_level": "low",
                "should_escalate": False
            }

        # 5. Extract questions from protocol
        questions = protocol.questions if protocol and protocol.questions else []
        clinical_questions = [
            q for q in sorted(questions, key=lambda q: q.sequence_order)
            if q.category.lower() != "greeting" and "few minutes" not in q.question_text.lower()
        ]
        if not clinical_questions:
            clinical_questions = sorted(questions, key=lambda q: q.sequence_order)

        # Determine current active step (1 to 5)
        # Turn 0 was greeting. Turns 1..5 map sequentially to questions, or adapt based on content
        step_idx = min(5, max(1, turn_count))
        target_q_text = clinical_questions[min(step_idx - 1, len(clinical_questions) - 1)].question_text if clinical_questions else "How is your recovery progressing?"

        checklist_step_labels = {
            1: "Daily Weight & Shortness of Breath",
            2: "Swelling in Extremities",
            3: "Medication Adherence",
            4: "Follow-Up Clinic Appointment",
            5: "Open Questions & Conclude"
        }

        # 6. Build Context for Groq LLM
        patient_context = {
            "name": f"{patient.first_name} {patient.last_name}",
            "patient_id": patient.id,
            "mrn": patient.mrn,
            "condition": (protocol.target_condition if hasattr(protocol, "target_condition") else getattr(protocol, "condition", "Recovery")) if protocol else "Recovery",
            "hospital_name": hospital.name,
            "contact_phone": hospital.contact_phone,
            "attempt_number": 1
        }

        protocol_context = {
            "checklist_step": step_idx,
            "current_step": checklist_step_labels.get(step_idx, "Daily Weight & Shortness of Breath"),
            "active_question": target_q_text
        }

        # 7. Generate context-aware response via Groq LLM
        llm_output: ChatbotOutput = groq_service.generate_chat_response(
            patient_message=latest_patient_speech,
            conversation_history=dialogue_history,
            patient_context=patient_context,
            protocol_context=protocol_context,
            deterministic_safety=det_safety
        )

        # 8. Assemble structured result
        action = "ESCALATE_NOW" if (llm_output.should_escalate or det_safety["should_escalate"]) else "CONTINUE"
        chk_step = llm_output.checklist_step or step_idx

        return {
            "speaker": "AGENT",
            "text": llm_output.response,
            "turn_index": turn_count,
            "stage": llm_output.protocol_step.upper(),
            "checklist_step": chk_step,
            "action": action,
            "intent": llm_output.intent,
            "risk_level": llm_output.risk_level,
            "next_protocol_step": llm_output.next_protocol_step,
            "needs_followup": llm_output.needs_followup,
            "should_escalate": (llm_output.should_escalate or det_safety["should_escalate"])
        }

voice_intake_agent = VoiceIntakeAgent()

