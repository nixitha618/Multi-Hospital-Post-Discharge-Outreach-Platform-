# AI Usage Documentation: Multi-Agent Architecture, Schemas & Controlled Tools

## 1. Multi-Agent System Architecture

The AI layer partitions responsibilities across four distinct specialized agents:

1. **Voice Intake Agent (`backend/app/ai/intake_agent.py`)**
   - **Role**: Conducts protocol-guided dialogue with the patient.
   - **Flow**: Identity Verification -> Availability & Consent -> Protocol Questions -> Clarification & Empathy -> Warm Transfer / Wrap-up.
   - **Safety Boundary**: Never provides unsupported medical advice or diagnoses.

2. **Clinical Triage Agent (`backend/app/ai/triage_agent.py`)**
   - **Role**: Translates patient conversational utterances into structured clinical observations.
   - **Output**: Validated `StructuredTriageOutput` schema containing observed symptom indicators, severity, quotes, protocol citations, and triage classification (`ROUTINE`, `CONCERNING`, `URGENT`, `UNCERTAIN`).

3. **Escalation Consensus Engine (`backend/app/ai/consensus_engine.py`)**
   - **Role**: Combines multi-path evaluations (Clinical Acuity Assessor + Protocol Adherence Assessor + Safety Arbiter).
   - **Consensus Policy**: Conservative safety policy. Disagreements are explicitly detected and escalated.

4. **Clinical Documentation Agent (`backend/app/ai/documentation_agent.py`)**
   - **Role**: Formats complete encounter into standardized SOAP documentation and commits FHIR Communication and Observation resources to the Mock EHR.

---

## 2. Controlled AI Tool Bus (`backend/app/ai/controlled_tools.py`)

AI agents **never touch the database directly**. All interactions must execute through the controlled tool bus following this strict pattern:

$$\text{AI Tool Request} \longrightarrow \text{Tenant Authorization} \longrightarrow \text{Schema Validation} \longrightarrow \text{Business Rules} \longrightarrow \text{Execution} \longrightarrow \text{Audit Log} \longrightarrow \text{Result}$$

### Supported Controlled Tools:
- `patient_lookup`: Scoped strictly to the requesting hospital tenant. Rejects cross-tenant patient access.
- `encounter_lookup`: Retrieves discharge summary and attending physician notes.
- `protocol_search`: Retrieves hospital-specific clinical protocols and red-flag rules.
- `callback_scheduling`: Explicitly schedules a patient callback timestamp.
- `escalation_creation`: Creates an open human-in-the-loop clinical escalation record.
- `mock_ehr_update`: Commits FHIR Communication resources to the Mock EHR.

---

## 3. Structured Output Schemas & Validation

All AI outputs are validated at runtime against strict Pydantic models:
- `StructuredTriageOutput`:
  - `triage_classification`: Enum (`ROUTINE`, `CONCERNING`, `URGENT`, `UNCERTAIN`)
  - `confidence`: float (0.0 to 1.0)
  - `observed_indicators`: List of `ObservedIndicator` (symptom key, presence, quote, severity)
  - `protocol_references`: List of string citations
  - `clinical_reasoning`: Explanation string
  - `escalation_recommended`: Boolean
- `EscalationConsensusResult`:
  - `consensus_decision`: Enum
  - `escalate_to_human`: Boolean
  - `agreement`: Boolean
  - `disagreement_detected`: Boolean
  - `votes`: List of individual evaluator votes
