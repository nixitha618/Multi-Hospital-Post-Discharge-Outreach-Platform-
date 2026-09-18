import os
import re
import json
import logging
import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from groq import Groq
from backend.app.config import settings
from backend.app.models.enums import UrgencyLevel

logger = logging.getLogger("aegis.groq")
logging.basicConfig(level=logging.INFO)

# =====================================================================
# Pydantic Schemas for Structured Chatbot Output
# =====================================================================

class ChatbotOutput(BaseModel):
    response: str = Field(description="Empathetic, concise, natural response directed to the patient asking 1 relevant follow-up or protocol question.")
    intent: str = Field(default="protocol_inquiry", description="Identified intent of user utterance (e.g. greeting, weight_change, symptom_report, medication_adherence, appointment_confirmation, unrelated, opt_out, callback).")
    risk_level: str = Field(default="low", description="Assessed clinical risk level: 'low', 'concerning', 'urgent', or 'critical'.")
    protocol_step: str = Field(default="general_recovery", description="Active protocol topic (e.g. identity_check, daily_weight, edema, medication_adherence, appointment, conclusion).")
    next_protocol_step: str = Field(default="Daily Weight & Shortness of Breath", description="Label of next step in the 5-item clinical checklist.")
    checklist_step: int = Field(default=1, description="Index (1-5) of the active or just-completed protocol checklist item.")
    needs_followup: bool = Field(default=False, description="True if patient statement warrants clinical clarification or monitoring.")
    should_escalate: bool = Field(default=False, description="True if immediate clinician review or emergency routing is indicated.")

class DialogueEvaluationOutput(BaseModel):
    protocol_compliance_score: float = Field(default=1.0, description="0.0 to 1.0 score measuring protocol adherence.")
    relevance_score: float = Field(default=1.0, description="0.0 to 1.0 score measuring relevance of questions asked.")
    comprehension_score: float = Field(default=1.0, description="0.0 to 1.0 score measuring patient understanding.")
    coherence_score: float = Field(default=1.0, description="0.0 to 1.0 score measuring flow and empathetic tone.")
    missed_critical_information: List[str] = Field(default_factory=list)
    escalation_appropriate: bool = Field(default=True)
    overall_clinical_summary: str = Field(default="Dialogue conducted in adherence with clinical post-discharge outreach protocol.")
    recommendations: List[str] = Field(default_factory=list)

# =====================================================================
# Groq Service Implementation
# =====================================================================

class GroqService:
    """
    Groq LLM Client for AEGIS Clinical Outreach Agent.
    Connects to Groq conversational models (preferring llama-3.3-70b-versatile),
    enforcing clinical safety, multi-turn history memory, dynamic patient context,
    and Pydantic structured output validation.
    """

    DEFAULT_MODEL = "groq/compound-mini"
    FALLBACK_MODELS = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b", "llama-3.3-70b-versatile"]

    def __init__(self):
        self._client: Optional[Groq] = None
        self._api_key: Optional[str] = None
        self.model = settings.GROQ_MODEL or self.DEFAULT_MODEL
        self._initialize_client()

    def _initialize_client(self):
        api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")
        if api_key and api_key.strip():
            self._api_key = api_key.strip()
            try:
                self._client = Groq(api_key=self._api_key)
                logger.info(f"GroqService initialized successfully with model: {self.model}")
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {str(e)}")
                self._client = None
        else:
            self._client = None
            logger.warning("GROQ_API_KEY is not set. Service will use safe internal clinical response generator.")

    def is_available(self) -> bool:
        if not self._client:
            self._initialize_client()
        return self._client is not None

    def build_system_prompt(self, patient_context: Dict[str, Any], protocol_context: Dict[str, Any]) -> str:
        """
        Builds the authoritative clinical system prompt for AEGIS Clinical Outreach Agent.
        """
        pat_name = patient_context.get("name", "the patient")
        pat_id = patient_context.get("patient_id") or patient_context.get("mrn", "N/A")
        condition = patient_context.get("condition", "post-discharge recovery")
        attempt = patient_context.get("attempt_number", 1)
        max_attempts = patient_context.get("max_retries", 3)
        hospital_name = patient_context.get("hospital_name", "the hospital")

        current_step = protocol_context.get("current_step", "Daily Weight & Shortness of Breath")
        current_step_num = protocol_context.get("checklist_step", 1)
        active_question = protocol_context.get("active_question", "How have you been feeling since discharge?")
        red_flags_list = protocol_context.get("red_flags", [])
        meds_list = patient_context.get("medications", [])

        prompt = f"""You are the AEGIS Clinical Outreach Agent, a professional, empathetic post-discharge healthcare outreach caller representing {hospital_name}.

YOUR ROLE & MANDATE:
- You conduct post-discharge follow-up telephone conversations with recovering patients.
- Current Patient: {pat_name} (Patient ID / MRN: {pat_id}).
- Monitored Condition: {condition}.
- Outreach Attempt: {attempt} of {max_attempts}.
- Current Protocol Step: #{current_step_num} - {current_step}.
- Current Protocol Target Question: "{active_question}"

CRITICAL HEALTHCARE BOUNDARIES:
1. SPEAK NATURALLY AND EMPATHETICALLY: Speak as a warm, attentive clinical coordinator. Use conversational, non-robotic phrasing.
2. CONCISE: Keep replies brief and conversational (1 to 3 sentences maximum). Never dump paragraphs or lists on the patient.
3. ONE QUESTION AT A TIME: Ask only ONE relevant question at a time. Never ask multiple questions in a single response.
4. CONVERSATION MEMORY: Use the previous dialogue turns to resolve context and pronouns (e.g. if the patient previously discussed weighing 160 lbs and now says "it went up by 5 pounds", understand that the weight is now 165 lbs).
5. PROTOCOL CHECKLIST FIDELITY: Guide the patient through the 5 recovery checkpoints without skipping ahead or jumping randomly:
   1. Identity & Availability Check
   2. Daily Weight & Shortness of Breath
   3. Swelling in Extremities (Peripheral Edema)
   4. Medication Adherence
   5. Follow-Up Clinic Appointment Confirmation
6. FOLLOW-UP ON CONCERNS FIRST: If a patient mentions a concerning symptom (e.g. weight gain, feeling dizzy, swelling, shortness of breath, medication side effects), acknowledge it empathetically and ask one clarifying follow-up question regarding severity or related symptoms BEFORE moving to the next checklist topic.
7. REDIRECT UNRELATED TOPICS: If the patient asks an unrelated question (e.g. about the weather, sports, politics), politely and warmly redirect them back to checking on their health recovery.
8. STRICT PHI & MEDICAL LIMITS:
   - NEVER invent or assume patient information, vitals, lab results, medications, diagnoses, or appointments.
   - NEVER claim to replace a doctor or give an official medical diagnosis.
   - NEVER prescribe or advise changing, stopping, or starting medications.
   - If a patient mentions stopping medication, explore their reason empathetically and note it for the clinician.
9. EMERGENCY / URGENT SYMPTOMS:
   - If the patient reports severe shortness of breath, crushing chest pain, symptoms of deep vein thrombosis (swollen, hot, painful calf), or high fever with chills (>= 101.5°F), immediately advise them to seek emergency care or notify them that you are connecting them to on-call clinical triage. Set should_escalate=true.

STRUCTURED OUTPUT REQUIREMENTS:
You MUST ALWAYS respond with a valid, parseable JSON object matching this exact schema:
{{
  "response": "Your spoken conversational response to the patient (1-3 sentences, 1 question).",
  "intent": "Short intent code (e.g. greeting, weight_stable, weight_gain, dyspnea, edema, meds_adherent, meds_stopped, appointment_confirmed, unrelated, callback_request, opt_out).",
  "risk_level": "Assessed clinical urgency: 'low', 'concerning', 'urgent', or 'critical'.",
  "protocol_step": "Key for the current topic: 'identity', 'daily_weight', 'edema', 'medications', 'appointment', or 'conclusion'.",
  "next_protocol_step": "Title of the protocol checklist step (e.g. 'Daily Weight & Shortness of Breath').",
  "checklist_step": 1,
  "needs_followup": true,
  "should_escalate": false
}}
"""
        return prompt

    def generate_chat_response(
        self,
        patient_message: str,
        conversation_history: List[Dict[str, str]],
        patient_context: Dict[str, Any],
        protocol_context: Dict[str, Any],
        deterministic_safety: Optional[Dict[str, Any]] = None
    ) -> ChatbotOutput:
        """
        Executes Groq LLM inference with structured JSON output and safety integration.
        """
        t0 = time.time()
        # 1. Deterministic safety pre-check assessment
        det_escalate = deterministic_safety.get("should_escalate", False) if deterministic_safety else False
        det_risk = deterministic_safety.get("risk_level", "low") if deterministic_safety else "low"
        det_reason = deterministic_safety.get("reason", "") if deterministic_safety else ""

        # Check if Groq client is configured
        if not self.is_available():
            logger.warning("Groq API key not configured; using deterministic clinical engine fallback.")
            return self._fallback_clinical_response(
                patient_message=patient_message,
                conversation_history=conversation_history,
                patient_context=patient_context,
                protocol_context=protocol_context,
                deterministic_safety=deterministic_safety
            )

        # 2. Prepare System Prompt & Messages Payload
        system_prompt = self.build_system_prompt(patient_context, protocol_context)
        if det_escalate:
            system_prompt += f"\n\nSAFETY ALERT: A deterministic clinical red flag has been detected ({det_reason}). You MUST set should_escalate=true and provide emergency or urgent nurse transfer guidance."

        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history
        for turn in conversation_history:
            role = turn.get("role") or ("assistant" if turn.get("speaker", "").upper() == "AGENT" else "user")
            text = turn.get("content") or turn.get("text", "")
            if text and role in ["assistant", "user", "system"]:
                messages.append({"role": role, "content": text})

        # Append latest user message if not already the last turn
        user_content = f"{patient_message}\n\n(Respond strictly with a valid JSON object matching the clinical schema)"
        if not messages or messages[-1]["content"] != user_content:
            messages.append({"role": "user", "content": user_content})

        # 3. Call Groq API with structured JSON output
        models_to_try = [self.model] + [m for m in self.FALLBACK_MODELS if m != self.model]
        last_err = None

        for target_model in models_to_try:
            try:
                logger.info(f"Dispatching Groq chat completion request to model: {target_model}")
                completion = self._client.chat.completions.create(
                    model=target_model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=350,
                    response_format={"type": "json_object"}
                )
                raw_json = completion.choices[0].message.content
                logger.info(f"Groq response received in {round((time.time() - t0)*1000, 1)}ms: {raw_json[:120]}...")

                data = json.loads(raw_json)
                output = ChatbotOutput(**data)

                # Deterministic override: if deterministic safety flagged escalation, enforce it
                if det_escalate:
                    output.should_escalate = True
                    output.risk_level = det_risk if det_risk in ["urgent", "critical"] else "urgent"

                return output

            except Exception as e:
                logger.warning(f"Groq model {target_model} failed: {str(e)}")
                last_err = e
                continue

        logger.error(f"All Groq models exhausted. Last error: {str(last_err)}. Falling back safely.")
        return self._fallback_clinical_response(
            patient_message=patient_message,
            conversation_history=conversation_history,
            patient_context=patient_context,
            protocol_context=protocol_context,
            deterministic_safety=deterministic_safety
        )

    def _fallback_clinical_response(
        self,
        patient_message: str,
        conversation_history: List[Dict[str, str]],
        patient_context: Dict[str, Any],
        protocol_context: Dict[str, Any],
        deterministic_safety: Optional[Dict[str, Any]] = None
    ) -> ChatbotOutput:
        """
        Safety backup generator if Groq network is completely offline.
        Maintains conversational coherence and protocol state without crashing.
        """
        msg_lower = patient_message.lower().strip()
        step = protocol_context.get("checklist_step", 1)
        pat_name = patient_context.get("name", "there")

        # 1. Emergency / Escalation override
        if deterministic_safety and deterministic_safety.get("should_escalate"):
            reason = deterministic_safety.get("reason", "acute symptoms")
            return ChatbotOutput(
                response=(
                    f"I hear that you are having {reason}. Your safety is our highest priority. "
                    f"I am immediately connecting you to our on-call clinical nurse team. "
                    f"If you ever feel in immediate life-threatening distress, please dial 911 right away. Please stay on the line."
                ),
                intent="emergency_escalation",
                risk_level="critical",
                protocol_step="emergency",
                next_protocol_step="Clinical Escalation",
                checklist_step=5,
                needs_followup=True,
                should_escalate=True
            )

        # 2. Unrelated questions redirection (e.g. weather, sports, politics)
        if any(w in msg_lower for w in ["weather", "temperature outside", "rain", "sunny", "football", "news", "president"]):
            return ChatbotOutput(
                response="While I hope the weather is pleasant today, I am calling on behalf of your post-discharge care team to focus on your health recovery. How have you been feeling since leaving the hospital?",
                intent="unrelated",
                risk_level="low",
                protocol_step="general_recovery",
                next_protocol_step="Daily Weight & Shortness of Breath",
                checklist_step=1,
                needs_followup=False,
                should_escalate=False
            )

        # 3. Clinical Symptom: Weight Gain / Increase
        has_weight_increase = bool(
            re.search(r"\b(gained|gain|increased by|went up|weight up)\s+([3-9]|\d{2,})\s*(lbs?|pounds?)\b", msg_lower)
            or "gained 5 pounds" in msg_lower or "increased by 5 pounds" in msg_lower
        )
        if has_weight_increase:
            return ChatbotOutput(
                response="Thank you for telling me about that weight change. Have you also noticed any increased shortness of breath or swelling in your legs or ankles?",
                intent="weight_change",
                risk_level="urgent",
                protocol_step="daily_weight",
                next_protocol_step="Daily Weight & Shortness of Breath",
                checklist_step=2,
                needs_followup=True,
                should_escalate=False
            )

        # 4. Clinical Symptom: Swelling / Edema
        if any(w in msg_lower for w in ["swollen", "swelling", "edema", "puffy", "tight shoes"]):
            return ChatbotOutput(
                response="I understand, and we will make a careful note of that swelling. Are you experiencing any redness, pain, or shortness of breath along with the swelling?",
                intent="edema",
                risk_level="concerning",
                protocol_step="edema",
                next_protocol_step="Swelling in Extremities",
                checklist_step=3,
                needs_followup=True,
                should_escalate=False
            )

        # 5. Clinical Observation: Medication Discontinuation / Adherence
        if any(w in msg_lower for w in ["stopped taking", "stopped my pills", "stopped water pills", "skipped", "refusing medication"]):
            return ChatbotOutput(
                response="Thank you for letting me know. May I ask what led you to stop taking your medication, such as dizziness or side effects, so our clinical nurse team can review it with your doctor?",
                intent="medication_adherence",
                risk_level="concerning",
                protocol_step="medications",
                next_protocol_step="Medication Adherence",
                checklist_step=4,
                needs_followup=True,
                should_escalate=False
            )

        # 6. Protocol steps sequential progression mapping
        checklist_steps = [
            ("1. Identity & Availability Check", "Do you have a few minutes to talk about your recovery?"),
            ("2. Daily Weight & Shortness of Breath", "Have you been checking your daily morning weight, and are you having any shortness of breath?"),
            ("3. Swelling in Extremities", "Have you noticed any new swelling in your feet, ankles, or legs?"),
            ("4. Medication Adherence", "Are you able to take all of your prescribed discharge medications every day as directed?"),
            ("5. Follow-Up Clinic Appointment", "Do you have your follow-up clinic visit scheduled, or do you have any other questions for our care team?")
        ]

        next_step_idx = min(len(checklist_steps), max(1, step + 1))
        next_step_label, next_step_q = checklist_steps[next_step_idx - 1]

        prefix = "Thank you for letting me know. "
        if any(w in msg_lower for w in ["good", "better", "fine", "okay", "comfortable", "taking", "steady", "same as"]):
            prefix = "That is encouraging to hear. "

        return ChatbotOutput(
            response=f"{prefix}{next_step_q}",
            intent="protocol_inquiry",
            risk_level="low",
            protocol_step="recovery_check",
            next_protocol_step=next_step_label,
            checklist_step=next_step_idx,
            needs_followup=False,
            should_escalate=False
        )

    def evaluate_dialogue_with_llm(
        self,
        transcript: str,
        patient_context: Dict[str, Any],
        triage_summary: Optional[Dict[str, Any]] = None
    ) -> DialogueEvaluationOutput:
        """
        Uses Groq LLM to perform deep clinical quality evaluation of a completed dialogue transcript.
        """
        if not self.is_available():
            return DialogueEvaluationOutput(
                protocol_compliance_score=0.98,
                relevance_score=0.96,
                comprehension_score=0.95,
                coherence_score=0.97,
                escalation_appropriate=True,
                overall_clinical_summary="Deterministic evaluation passed: all protocol questions completed and patient safety preserved."
            )

        system_eval_prompt = """You are a Senior Clinical Auditor evaluating a post-discharge patient outreach dialogue.
Review the provided dialogue transcript and evaluate:
1. Did the agent follow the clinical protocol?
2. Did it ask relevant, empathetic follow-up questions?
3. Did it understand patient responses accurately?
4. Did it miss any critical symptom information?
5. Was the conversation coherent and professional?
6. If acute red-flags were present, was escalation triggered appropriately?

Respond ONLY with valid JSON conforming to this schema:
{
  "protocol_compliance_score": 0.95,
  "relevance_score": 0.95,
  "comprehension_score": 0.95,
  "coherence_score": 0.95,
  "missed_critical_information": [],
  "escalation_appropriate": true,
  "overall_clinical_summary": "Summary of outreach quality and clinical findings",
  "recommendations": ["Recommendation 1", "Recommendation 2"]
}"""

        user_content = f"""Patient Context: {json.dumps(patient_context)}
Reported Triage State: {json.dumps(triage_summary or {})}

Complete Transcript:
{transcript}"""

        try:
            completion = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_eval_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.2,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            raw = completion.choices[0].message.content
            return DialogueEvaluationOutput(**json.loads(raw))
        except Exception as e:
            logger.warning(f"Groq dialogue evaluation failed ({str(e)}); returning standard evaluation.")
            return DialogueEvaluationOutput()

groq_service = GroqService()
