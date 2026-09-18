import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.ai.groq_service import groq_service, ChatbotOutput
from backend.app.api.chat import _SESSION_MEMORY

@pytest.mark.asyncio
async def test_chat_endpoint_schema_and_routing():
    """Verify both /chat and /api/chat respond and adhere to the contract schema."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test POST /chat
        payload = {
            "message": "Hello, I am ready for the check-in.",
            "patient_context": {
                "name": "Theresa Kowalski",
                "patient_id": "SJM-100270",
                "condition": "CHF",
                "attempt_number": 2,
                "max_retries": 3,
                "hospital_name": "St. Jude Memorial Hospital"
            },
            "protocol_context": {
                "current_step": "Identity & Availability Check",
                "checklist_step": 1,
                "active_question": "Do you have a few minutes to talk about your recovery?"
            },
            "session_id": "test-session-001"
        }
        resp = await client.post("/chat", json=payload)
        assert resp.status_code == 200, f"Error: {resp.text}"
        data = resp.json()
        assert "response" in data
        assert "intent" in data
        assert "risk_level" in data
        assert "checklist_step" in data
        assert "should_escalate" in data
        assert data["session_id"] == "test-session-001"

        # 2. Test POST /api/chat
        resp2 = await client.post("/api/chat", json=payload)
        assert resp2.status_code == 200

@pytest.mark.asyncio
async def test_scenario_1_feeling_okay():
    """TEST 1: Patient says 'I am feeling okay.' -> Natural response & next protocol question."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/chat", json={
            "message": "I am feeling okay.",
            "patient_context": {"name": "Theresa Kowalski", "condition": "CHF"},
            "protocol_context": {"current_step": "Daily Weight & Shortness of Breath", "checklist_step": 1},
            "session_id": "test-s1"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["response"]) > 10
        assert data["should_escalate"] is False

@pytest.mark.asyncio
async def test_scenario_2_weight_stable():
    """TEST 2: Patient says 'My weight is the same as yesterday.' -> LLM recognizes stable weight."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/chat", json={
            "message": "My weight is the same as yesterday.",
            "patient_context": {"name": "Theresa Kowalski", "condition": "CHF"},
            "protocol_context": {"current_step": "Daily Weight & Shortness of Breath", "checklist_step": 2},
            "session_id": "test-s2"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["should_escalate"] is False
        assert data["risk_level"] in ["low", "routine"]

@pytest.mark.asyncio
async def test_scenario_3_weight_gain_5_pounds():
    """TEST 3: Patient says 'I gained 5 pounds since yesterday.' -> Recognizes weight change and asks follow-up."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/chat", json={
            "message": "I gained 5 pounds since yesterday.",
            "patient_context": {"name": "Theresa Kowalski", "condition": "CHF"},
            "protocol_context": {"current_step": "Daily Weight & Shortness of Breath", "checklist_step": 2},
            "session_id": "test-s3"
        })
        assert resp.status_code == 200
        data = resp.json()
        # Should flag risk or follow-up
        assert data["risk_level"] in ["concerning", "urgent", "critical"] or data["needs_followup"] is True
        assert any(w in data["response"].lower() for w in ["breath", "swelling", "pound", "weight", "legs", "ankles", "doctor", "nurse"])

@pytest.mark.asyncio
async def test_scenario_4_trouble_breathing_acute_escalation():
    """TEST 4: Patient says 'I am having trouble breathing.' -> Immediate safety escalation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/chat", json={
            "message": "I am having trouble breathing.",
            "patient_context": {"name": "Theresa Kowalski", "condition": "CHF"},
            "protocol_context": {"current_step": "Daily Weight & Shortness of Breath", "checklist_step": 2},
            "session_id": "test-s4"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["should_escalate"] is True
        assert data["risk_level"] in ["urgent", "critical"]

@pytest.mark.asyncio
async def test_scenario_5_legs_very_swollen():
    """TEST 5: Patient says 'My legs are very swollen.' -> Concerning edema follow-up."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/chat", json={
            "message": "My legs are very swollen.",
            "patient_context": {"name": "Theresa Kowalski", "condition": "CHF"},
            "protocol_context": {"current_step": "Swelling in Extremities", "checklist_step": 3},
            "session_id": "test-s5"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_level"] in ["concerning", "urgent"] or data["needs_followup"] is True

@pytest.mark.asyncio
async def test_scenario_6_stopped_water_pills():
    """TEST 6: Patient says 'I stopped taking my water pills.' -> Flags medication non-adherence."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/chat", json={
            "message": "I stopped taking my water pills.",
            "patient_context": {"name": "Theresa Kowalski", "condition": "CHF"},
            "protocol_context": {"current_step": "Medication Adherence", "checklist_step": 4},
            "session_id": "test-s6"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_level"] in ["concerning", "urgent"] or "med" in data["intent"] or data["needs_followup"] is True

@pytest.mark.asyncio
async def test_scenario_7_conversation_memory():
    """TEST 7: Conversation memory test: multi-turn context reference."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = "test-memory-session"

        # Turn 1: AI asked weight, patient says 160 pounds
        resp1 = await client.post("/chat", json={
            "message": "160 pounds.",
            "conversation_history": [
                {"role": "assistant", "content": "How much do you weigh today?"}
            ],
            "patient_context": {"name": "Theresa Kowalski", "condition": "CHF"},
            "session_id": session_id
        })
        assert resp1.status_code == 200

        # Turn 2: AI asked about weight change, patient says it increased by 5 pounds
        resp2 = await client.post("/chat", json={
            "message": "Yes, it increased by 5 pounds.",
            "conversation_history": [
                {"role": "assistant", "content": "How much do you weigh today?"},
                {"role": "user", "content": "160 pounds."},
                {"role": "assistant", "content": "Has your weight changed recently?"}
            ],
            "patient_context": {"name": "Theresa Kowalski", "condition": "CHF"},
            "session_id": session_id
        })
        assert resp2.status_code == 200
        data = resp2.json()
        # Should understand 5 pound increase on 160 lbs
        assert data["risk_level"] in ["concerning", "urgent", "critical"] or data["needs_followup"] is True

@pytest.mark.asyncio
async def test_scenario_8_unrelated_redirection():
    """TEST 8: Patient says 'What is the weather today?' -> Polite clinical redirection."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/chat", json={
            "message": "What is the weather today?",
            "patient_context": {"name": "Theresa Kowalski", "condition": "CHF"},
            "protocol_context": {"current_step": "Daily Weight & Shortness of Breath"},
            "session_id": "test-s8"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["should_escalate"] is False
        # Response should redirect back to recovery or health
        assert any(w in data["response"].lower() for w in ["recovery", "health", "check", "feeling", "care", "today", "discharge", "hospital"])

@pytest.mark.asyncio
async def test_error_resilience_offline_fallback():
    """Verify service continuity when Groq is unavailable."""
    # Temporarily set invalid client
    original_client = groq_service._client
    try:
        groq_service._client = None
        output = groq_service.generate_chat_response(
            patient_message="I feel fine today.",
            conversation_history=[],
            patient_context={"name": "Test Patient", "condition": "CHF"},
            protocol_context={"checklist_step": 1}
        )
        assert isinstance(output, ChatbotOutput)
        assert len(output.response) > 5
        assert output.should_escalate is False
    finally:
        groq_service._client = original_client
