from typing import Dict, Any
from fastapi import APIRouter, Depends
from backend.app.api.deps import get_tenant_id
from backend.app.ehr.mock_service import mock_ehr_service

router = APIRouter(prefix="/ehr", tags=["Mock EHR Registry"])

@router.get("/records")
async def get_ehr_records(
    tenant_id: str = Depends(get_tenant_id)
) -> Dict[str, Any]:
    """
    Inspects FHIR-like resources currently synchronized to the Mock EHR external system.
    """
    return {
        "hospital_id": tenant_id,
        "communications": mock_ehr_service.communications.get(tenant_id, []),
        "observations": mock_ehr_service.observations.get(tenant_id, []),
        "tasks": mock_ehr_service.tasks.get(tenant_id, []),
        "gateway_status": "ONLINE" if not mock_ehr_service.simulate_failure else "DEGRADED"
    }

@router.post("/simulate-failure")
async def toggle_simulate_failure(
    enable: bool
):
    mock_ehr_service.simulate_failure = enable
    return {"simulated_failure_active": mock_ehr_service.simulate_failure}
