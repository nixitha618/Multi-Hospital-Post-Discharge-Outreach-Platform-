import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.app.ehr.base import EHRClient
from backend.app.time_utils import get_ist_iso
from backend.app.ehr.fhir_models import FHIRObservation, FHIRCommunication, FHIRTask

class MockEHRService(EHRClient):
    """
    In-memory / observable Mock EHR Service implementing standard EHRClient.
    Maintains a simulated external healthcare system registry of communications, observations, and tasks.
    """

    def __init__(self):
        # tenant_id -> list of records
        self.communications: Dict[str, List[Dict[str, Any]]] = {}
        self.observations: Dict[str, List[Dict[str, Any]]] = {}
        self.tasks: Dict[str, List[Dict[str, Any]]] = {}
        self.simulate_failure: bool = False

    async def get_patient(self, hospital_id: str, patient_id: str) -> Optional[Dict[str, Any]]:
        # In mock implementation, patient details are queried from platform db
        return {
            "resourceType": "Patient",
            "id": patient_id,
            "managingOrganization": hospital_id,
            "status": "active"
        }

    async def get_encounter(self, hospital_id: str, encounter_id: str) -> Optional[Dict[str, Any]]:
        return {
            "resourceType": "Encounter",
            "id": encounter_id,
            "status": "finished",
            "serviceProvider": hospital_id
        }

    async def get_clinical_history(self, hospital_id: str, patient_id: str) -> Dict[str, Any]:
        return {
            "patient_id": patient_id,
            "hospital_id": hospital_id,
            "active_conditions": ["CHF (I50.9)", "Hypertension (I10)"],
            "medications": ["Furosemide 40mg daily", "Lisinopril 10mg daily"]
        }

    async def post_communication(self, hospital_id: str, communication: FHIRCommunication) -> Dict[str, Any]:
        if self.simulate_failure:
            raise RuntimeError("Mock EHR Gateway Timeout: 504 Simulated Connection Reset")
        
        record_id = communication.id or f"ehr-comm-{uuid.uuid4().hex[:8]}"
        data = {
            "id": record_id,
            "hospital_id": hospital_id,
            "resourceType": communication.resourceType,
            "status": communication.status,
            "subject": communication.subject_reference,
            "topic": communication.topic,
            "sent": communication.sent.isoformat(),
            "payload_content": communication.payload_content,
            "synced_at": get_ist_iso()
        }
        
        if hospital_id not in self.communications:
            self.communications[hospital_id] = []
        self.communications[hospital_id].append(data)
        return {"status": "SUCCESS", "resource_id": record_id, "synced_at": data["synced_at"]}

    async def post_observations(self, hospital_id: str, observations: List[FHIRObservation]) -> List[Dict[str, Any]]:
        if self.simulate_failure:
            raise RuntimeError("Mock EHR Gateway Timeout: 504 Simulated Connection Reset")
        
        results = []
        if hospital_id not in self.observations:
            self.observations[hospital_id] = []

        for obs in observations:
            obs_id = obs.id or f"ehr-obs-{uuid.uuid4().hex[:8]}"
            data = {
                "id": obs_id,
                "hospital_id": hospital_id,
                "resourceType": obs.resourceType,
                "status": obs.status,
                "code": obs.code.model_dump(),
                "subject": obs.subject_reference,
                "effectiveDateTime": obs.effectiveDateTime.isoformat(),
                "valueString": obs.valueString,
                "interpretation": obs.interpretation,
                "synced_at": get_ist_iso()
            }
            self.observations[hospital_id].append(data)
            results.append({"status": "SUCCESS", "resource_id": obs_id})
        
        return results

    async def create_followup_task(self, hospital_id: str, task: FHIRTask) -> Dict[str, Any]:
        if self.simulate_failure:
            raise RuntimeError("Mock EHR Gateway Timeout: 504 Simulated Connection Reset")
        
        task_id = task.id or f"ehr-task-{uuid.uuid4().hex[:8]}"
        data = {
            "id": task_id,
            "hospital_id": hospital_id,
            "resourceType": task.resourceType,
            "status": task.status,
            "priority": task.priority,
            "description": task.description,
            "patient": task.for_patient_reference,
            "authoredOn": task.authoredOn.isoformat(),
            "requester": task.requester,
            "owner": task.owner,
            "synced_at": get_ist_iso()
        }
        
        if hospital_id not in self.tasks:
            self.tasks[hospital_id] = []
        self.tasks[hospital_id].append(data)
        return {"status": "SUCCESS", "resource_id": task_id}

# Singleton instance for the application
mock_ehr_service = MockEHRService()
