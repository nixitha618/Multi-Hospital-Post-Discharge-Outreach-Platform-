from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.app.models.patient import Patient
from backend.app.models.protocol import ClinicalProtocol
from backend.app.models.organization import Hospital

class VoiceIntakeAgent:
    """
    Voice Intake & Conversation Agent.
    Orchestrates protocol-driven structured conversational turns with the patient,
    captures symptom statements, and guides safe clinical dialogue.
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
        and determines if the call should continue, reschedule, or end.
        """
        speech_lower = latest_patient_speech.lower()
        turn_count = len([d for d in dialogue_history if d.get("speaker") == "AGENT"])

        # Check emergency immediate alert
        if any(w in speech_lower for w in ["chest pain", "can't breathe", "cannot breathe", "barely breathe", "fainted", "passing out", "severe pain 10"]):
            return {
                "speaker": "AGENT",
                "text": (
                    f"I hear that you are experiencing severe symptoms ({latest_patient_speech.strip()}). "
                    f"Your safety is our highest priority. I am immediately connecting you to our on-call clinical nurse team, "
                    f"and if you ever feel in immediate life-threatening distress, please dial 911 right away. Please stay on the line."
                ),
                "turn_index": turn_count,
                "stage": "EMERGENCY_TRANSFER",
                "checklist_step": 5,
                "action": "ESCALATE_NOW",
                "intent": "emergency_escalation"
            }

        # Check callback request
        if any(w in speech_lower for w in ["busy right now", "call me back", "driving", "bad time", "call later"]):
            return {
                "speaker": "AGENT",
                "text": (
                    "I completely understand. When would be a more convenient time today for a clinical coordinator to call you back?"
                ),
                "turn_index": turn_count,
                "stage": "CALLBACK_REQUEST",
                "checklist_step": 0,
                "action": "SCHEDULE_CALLBACK",
                "intent": "callback_negotiation"
            }

        # Check opt-out / decline
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
                "intent": "opt_out"
            }

        # Filter protocol questions: skip the initial greeting since Turn 0 already greeted
        questions = protocol.questions if protocol and protocol.questions else []
        clinical_questions = [
            q for q in sorted(questions, key=lambda q: q.sequence_order)
            if q.category.lower() != "greeting" and "few minutes" not in q.question_text.lower()
        ]
        if not clinical_questions:
            clinical_questions = sorted(questions, key=lambda q: q.sequence_order)

        # Mapping for the 5-item UI checklist
        checklist_map = {
            "weight_gain_lbs": 1,
            "shortness_of_breath": 1,
            "peripheral_edema": 2,
            "medication_adherence": 3,
            "followup_appointment_scheduled": 4,
            "pain_score": 1,
            "calf_pain_dvt": 2,
            "incision_erythema": 3,
            "anticoagulant_adherence": 4,
            "general_status": 1,
            "fever_chills": 2,
            "tachycardia_dyspnea": 3,
            "antibiotic_adherence": 4
        }

        # q_idx corresponds to turn_count - 1
        q_idx = turn_count - 1
        if 0 <= q_idx < len(clinical_questions):
            target_q = clinical_questions[q_idx]
            q_text = target_q.question_text.replace("{hospital_name}", hospital.name)

            # Contextual empathetic transition
            prefix = ""
            if any(w in speech_lower for w in ["better", "good", "yes", "okay", "fine", "steady", "taking meds", "no problems"]):
                prefix = "That is encouraging to hear. "
            elif any(w in speech_lower for w in ["not good", "hurts", "pain", "swollen", "fever", "stopped"]):
                prefix = "I'm sorry to hear that you are having discomfort. We will note that carefully. "

            reply = f"{prefix}{q_text}"
            chk_step = checklist_map.get(target_q.expected_observation_key, min(4, q_idx + 1))
            return {
                "speaker": "AGENT",
                "text": reply,
                "turn_index": turn_count,
                "stage": target_q.category.upper(),
                "checklist_step": chk_step,
                "action": "CONTINUE",
                "expected_key": target_q.expected_observation_key,
                "intent": "protocol_inquiry"
            }
        elif q_idx == len(clinical_questions):
            # Ask if patient has any questions of their own
            return {
                "speaker": "AGENT",
                "text": "Thank you for answering those check-in questions. Do you have any questions or concerns about your medications, recovery, or discharge instructions?",
                "turn_index": turn_count,
                "stage": "OPEN_QUESTIONS",
                "checklist_step": 4,
                "action": "CONTINUE",
                "intent": "open_inquiry"
            }
        else:
            # If patient says no / nothing else, conclude call and auto-evaluate
            if any(w in speech_lower for w in ["no", "none", "nothing", "that's all", "thats all", "all set", "bye", "goodbye"]):
                wrapup = (
                    f"Thank you so much for your time today, {patient.first_name}. "
                    f"I have recorded all your recovery answers in your medical chart. "
                    f"If you ever need assistance, please call {hospital.name} at {hospital.contact_phone}. "
                    f"Concluding check-in encounter and finalizing clinical documentation..."
                )
                return {
                    "speaker": "AGENT",
                    "text": wrapup,
                    "turn_index": turn_count,
                    "stage": "CLOSING",
                    "checklist_step": 5,
                    "action": "AUTO_FINISH",
                    "intent": "call_conclusion"
                }
            else:
                # Dynamic response to patient question, keeping conversation open
                return {
                    "speaker": "AGENT",
                    "text": f"I have documented: '{latest_patient_speech.strip()}'. Our clinical care team will make a note of this. Do you have any other questions, or are you all set?",
                    "turn_index": turn_count,
                    "stage": "OPEN_QUESTIONS",
                    "checklist_step": 5,
                    "action": "CONTINUE",
                    "intent": "open_inquiry"
                }

voice_intake_agent = VoiceIntakeAgent()
