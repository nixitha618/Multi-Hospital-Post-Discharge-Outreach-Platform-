from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from backend.app.ehr.fhir_models import FHIRObservation, FHIRCommunication, FHIRTask

class EHRClient(ABC):
    """
    Abstract EHR Interface.
    Can be backed by MockEHRService (in prototype) or real SMART-on-FHIR / Epic / Cerner client.
    """

    @abstractmethod
    async def get_patient(self, hospital_id: str, patient_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve patient demographic and contact data."""
        pass

    @abstractmethod
    async def get_encounter(self, hospital_id: str, encounter_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve discharge encounter data."""
        pass

    @abstractmethod
    async def get_clinical_history(self, hospital_id: str, patient_id: str) -> Dict[str, Any]:
        """Retrieve conditions, medications, and previous encounters."""
        pass

    @abstractmethod
    async def post_communication(self, hospital_id: str, communication: FHIRCommunication) -> Dict[str, Any]:
        """Record an outreach call record / transcript as a FHIR Communication resource."""
        pass

    @abstractmethod
    async def post_observations(self, hospital_id: str, observations: List[FHIRObservation]) -> List[Dict[str, Any]]:
        """Commit structured clinical observations extracted from outreach call into EHR."""
        pass

    @abstractmethod
    async def create_followup_task(self, hospital_id: str, task: FHIRTask) -> Dict[str, Any]:
        """Create a clinical follow-up task or order for hospital nursing staff."""
        pass
