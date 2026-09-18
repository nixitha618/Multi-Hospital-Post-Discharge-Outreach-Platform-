import time
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from backend.app.ai.groq_service import groq_service, ChatbotOutput
from backend.app.ai.triage_agent import ClinicalTriageAgent

logger = logging.getLogger("aegis.chat_api")
logger.setLevel(logging.INFO)

router = APIRouter(tags=["AI Clinical Chatbot"])

# =====================================================================
# Request / Response Schemas
# =====================================================================

class ChatRequest(BaseModel):
    message: str = Field(..., description="Patient input utterance / response text.")
    conversation_history: Optional[List[Dict[str, str]]] = Field(default=None, description="Previous turns in the conversation.")
    patient_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Structured patient details (name, patient_id, condition, attempt_number).")
    protocol_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Active protocol checkpoint context.")
    session_id: Optional[str] = Field(default=None, description="Unique session ID to maintain isolated conversation memory.")

class ChatResponse(BaseModel):
    response: str = Field(..., description="Spoken natural agent response to the patient.")
    intent: str = Field(default="protocol_inquiry", description="Categorized user utterance intent.")
    risk_level: str = Field(default="low", description="Clinical risk rating: 'low', 'concerning', 'urgent', or 'critical'.")
    protocol_step: str = Field(default="daily_weight", description="Key for current protocol topic.")
    next_protocol_step: str = Field(default="Daily Weight & Shortness of Breath", description="Label for next protocol checklist checkpoint.")
    checklist_step: int = Field(default=1, description="Numerical index (1-5) of active protocol checkpoint.")
    needs_followup: bool = Field(default=False, description="Whether statement needs clinical clarification.")
    should_escalate: bool = Field(default=False, description="Whether immediate clinical escalation or emergency transfer was triggered.")
    session_id: str = Field(..., description="Session identifier for conversation memory.")
    latency_ms: float = Field(default=0.0, description="Inference latency in milliseconds.")

# Isolated in-memory session cache per session_id / patient_id
_SESSION_MEMORY: Dict[str, List[Dict[str, str]]] = {}

def get_session_history(session_key: str) -> List[Dict[str, str]]:
    return _SESSION_MEMORY.setdefault(session_key, [])

def append_to_session_history(session_key: str, role: str, content: str):
    history = get_session_history(session_key)
    history.append({"role": role, "content": content})
    # Keep last 20 turns for token budget
    if len(history) > 20:
        _SESSION_MEMORY[session_key] = history[-20:]

# =====================================================================
# Chatbot Route
# =====================================================================

@router.post("/chat", response_model=ChatResponse)
@router.post("/api/chat", response_model=ChatResponse)
async def chat_interaction(request: ChatRequest):
    """
    AEGIS Clinical Outreach Agent Chat Interaction Endpoint.
    Integrates Groq LLM (llama-3.3-70b-versatile) for dynamic, empathetic post-discharge
    dialogue, backed by deterministic clinical red-flag guardrails and multi-turn memory.
    """
    t_start = time.time()
    
    # 1. Resolve Session ID
    pat_ctx = request.patient_context or {}
    session_id = request.session_id or pat_ctx.get("patient_id") or pat_ctx.get("task_id") or "session-default"

    proto_ctx = request.protocol_context or {}
    cur_step = proto_ctx.get("current_step", "Daily Weight & Shortness of Breath")
    
    logger.info(f"Chat request received for session: {session_id[:16]}... | Step: {cur_step}")

    # 2. Build / Resolve Conversation History
    if request.conversation_history is not None:
        history = list(request.conversation_history)
        _SESSION_MEMORY[session_id] = history
    else:
        history = get_session_history(session_id)

    # 3. Deterministic Clinical Safety Pre-Check using ClinicalTriageAgent
    msg_lower = request.message.lower().strip()
    det_safety = {"should_escalate": False, "risk_level": "low", "reason": "", "needs_followup": False}

    # Evaluate current message
    triage_eval = ClinicalTriageAgent.evaluate_transcript(
        transcript=request.message,
        patient_name=pat_ctx.get("name", "patient"),
        condition=pat_ctx.get("condition", "CHF")
    )

    # Evaluate multi-turn combined dialogue for contextual threshold breaches (e.g. baseline weight + increase)
    combined_text = " ".join([t.get("content", "") for t in history] + [request.message])
    combined_triage = ClinicalTriageAgent.evaluate_transcript(
        transcript=combined_text,
        patient_name=pat_ctx.get("name", "patient"),
        condition=pat_ctx.get("condition", "CHF")
    )

    all_indicators = triage_eval.observed_indicators + combined_triage.observed_indicators

    has_critical = any(i.severity == "CRITICAL" for i in all_indicators)
    has_urgent = any(i.severity == "URGENT" for i in all_indicators)
    has_concerning = any(i.severity == "CONCERNING" for i in all_indicators)

    if has_critical:
        det_safety["should_escalate"] = True
        det_safety["risk_level"] = "critical"
        det_safety["needs_followup"] = True
        det_safety["reason"] = triage_eval.clinical_reasoning or "critical acute symptoms"
        logger.warning(f"Deterministic Acute Red Flag detected in session {session_id}: {request.message[:40]}")
    elif has_urgent:
        det_safety["risk_level"] = "urgent"
        det_safety["needs_followup"] = True
        det_safety["reason"] = "urgent clinical threshold reached"
    elif has_concerning:
        det_safety["risk_level"] = "concerning"
        det_safety["needs_followup"] = True
        det_safety["reason"] = "concerning symptom reported"

    # Adversarial prompt injection defense
    if "ignore previous instructions" in msg_lower or "tell me i am 100% cured" in msg_lower:
        det_safety["should_escalate"] = True
        det_safety["risk_level"] = "urgent"
        det_safety["reason"] = "adversarial prompt override"
        logger.warning(f"Adversarial prompt injection attempt in session {session_id}")

    # 4. Dispatch to Groq LLM
    try:
        llm_output: ChatbotOutput = groq_service.generate_chat_response(
            patient_message=request.message,
            conversation_history=history,
            patient_context=pat_ctx,
            protocol_context=proto_ctx,
            deterministic_safety=det_safety
        )
    except Exception as e:
        logger.error(f"Error executing Groq chat response: {str(e)}")
        # Safe fallback
        llm_output = groq_service._fallback_clinical_response(
            patient_message=request.message,
            conversation_history=history,
            patient_context=pat_ctx,
            protocol_context=proto_ctx,
            deterministic_safety=det_safety
        )

    # 5. Enforce deterministic safety override
    if det_safety["should_escalate"]:
        llm_output.should_escalate = True
        llm_output.risk_level = det_safety["risk_level"]
    elif det_safety["risk_level"] in ["urgent", "concerning"] and llm_output.risk_level == "low":
        llm_output.risk_level = det_safety["risk_level"]
    
    if det_safety.get("needs_followup"):
        llm_output.needs_followup = True

    # 6. Update Session Memory
    append_to_session_history(session_id, "user", request.message)
    append_to_session_history(session_id, "assistant", llm_output.response)

    latency_ms = round((time.time() - t_start) * 1000, 2)
    logger.info(f"Chat response generated in {latency_ms}ms | Intent: {llm_output.intent} | Risk: {llm_output.risk_level} | Escalate: {llm_output.should_escalate}")

    return ChatResponse(
        response=llm_output.response,
        intent=llm_output.intent,
        risk_level=llm_output.risk_level,
        protocol_step=llm_output.protocol_step,
        next_protocol_step=llm_output.next_protocol_step,
        checklist_step=llm_output.checklist_step,
        needs_followup=llm_output.needs_followup,
        should_escalate=llm_output.should_escalate,
        session_id=session_id,
        latency_ms=latency_ms
    )
