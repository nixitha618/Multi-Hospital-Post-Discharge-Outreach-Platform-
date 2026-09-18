# Known Limitations and Production Roadmap

## 1. Intentional Prototype Tradeoffs

In accordance with the 3–4 day prototype specification (Section 31), engineering focus was prioritized on the operational core: **queue design, concurrency limits, multi-factor prioritization, retry backoffs, multi-tenancy, AI clinical triage, multi-agent consensus, and human-in-the-loop escalation**.

The following deliberate simplifications were made:

1. **Telephony Layer**:
   - *Prototype*: Implements an interactive deterministic web audio call simulator with speech synthesis/recognition and live audio waveform animation.
   - *Production Requirement*: Integration with SIP trunking / PSTN carriers (Twilio Voice, Amazon Connect, or WebRTC streaming) with bidirectional ultra-low latency audio websockets.

2. **EHR Integration**:
   - *Prototype*: Implements an extensible `EHRClient` abstraction backed by `MockEHRService` storing FHIR-aligned Communication, Observation, and Task models with fault injection capabilities.
   - *Production Requirement*: Certified SMART-on-FHIR R4 authentication, HL7 v2 ADT/ORM message feeds, Epic App Orchard / Cerner Ignite API integration, and FHIR subscription webhooks.

3. **Storage & Concurrency Scalability**:
   - *Prototype*: Async SQLite in WAL (Write-Ahead Logging) mode, providing zero external database setup and concurrent reads with serializable write locks.
   - *Production Requirement*: Managed PostgreSQL / Citus cluster with row-level security (RLS) policies per tenant, Redis cluster for distributed slot leases and Celery / Temporal for distributed workflow orchestration.

4. **Security & Regulatory Compliance**:
   - *Prototype*: Functional RBAC and tenant isolation enforced in application logic.
   - *Production Requirement*: Full HIPAA Business Associate Agreement (BAA) coverage, SOC 2 Type II compliance, encryption at rest with customer-managed keys (AWS KMS / GCP Cloud KMS), and end-to-end PHI de-identification in logs.

5. **Language & Clinical Protocols**:
   - *Prototype*: Preloaded with 3 hospital protocols (Congestive Heart Failure, Total Knee Arthroplasty, Post-Sepsis Care) in English.
   - *Production Requirement*: Multilingual medical translation models (Spanish, Cantonese, Vietnamese, Arabic) and protocol authoring studio with LOINC/SNOMED-CT terminology bindings.
