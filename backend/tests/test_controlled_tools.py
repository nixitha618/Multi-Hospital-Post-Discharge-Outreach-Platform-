import pytest
from backend.app.database import AsyncSessionLocal
from backend.app.ai.controlled_tools import controlled_tool_bus
from backend.app.schemas.ai import ControlledToolRequest

@pytest.mark.asyncio
async def test_controlled_tool_patient_lookup_authorized():
    async with AsyncSessionLocal() as db:
        req = ControlledToolRequest(
            tool_name="patient_lookup",
            arguments={"patient_id": "pat-hosp-mgh-001"},
            caller_agent="VoiceIntakeAgent"
        )
        res = await controlled_tool_bus.execute_tool(db, "hosp-mgh", req)
        assert res.success is True
        assert res.result is not None
        assert res.result["patient_id"] == "pat-hosp-mgh-001"
        assert res.audit_id is not None

@pytest.mark.asyncio
async def test_controlled_tool_cross_tenant_rejection():
    async with AsyncSessionLocal() as db:
        # Agent in hosp-sjm attempts to query a patient from hosp-mgh
        req = ControlledToolRequest(
            tool_name="patient_lookup",
            arguments={"patient_id": "pat-hosp-mgh-001"},
            caller_agent="AdversarialAgent"
        )
        res = await controlled_tool_bus.execute_tool(db, "hosp-sjm", req)
        # Must fail because pat-hosp-mgh-001 does not belong to hosp-sjm
        assert res.success is False
        assert "not found in tenant" in res.error_message.lower()
