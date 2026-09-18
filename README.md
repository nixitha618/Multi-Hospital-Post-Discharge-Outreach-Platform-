# AegisHealth: Multi-Hospital Post-Discharge Outreach Platform

> **Autonomous AI-Powered Patient Follow-Up, Clinical Triage & Hospital Outreach Operations Platform**  
> *Product Requirements Document — Version 2.0 Reference Implementation*

---

## Quick Start (Single Command Setup)

The entire platform runs out-of-the-box with Python 3.10+ and requires **zero external database or Node/npm dependencies**. The HTML5, CSS3, and JavaScript frontend is served directly by FastAPI.

### 1. Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### 2. Run the Platform
```bash
python -m uvicorn backend.app.main:app --port 8000 --reload
```

### 3. Access the Operations Portal
Open **[http://localhost:8000](http://localhost:8000)** in your browser.
API Swagger Documentation is available at **[http://localhost:8000/docs](http://localhost:8000/docs)**.

### 4. Run the Automated Test Suite
```bash
python -m pytest backend/tests -v
```

---

## Core System Capabilities

1. **Multi-Tenancy & Strict Data Isolation (PRD Sec 3, 4, 25)**:
   - 3 preloaded hospital tenants:
     - **Metro General Hospital (MGH)** — EST, 5 concurrent slots, CHF protocol focus
     - **St. Jude Memorial Health (SJM)** — CST, 4 concurrent slots, Orthopedics protocol focus
     - **Pacific Coast Medical (PCM)** — PST, 6 concurrent slots, Sepsis protocol focus
   - Tenant isolation enforced in backend data-access layer (`X-Tenant-ID`). Hospital A cannot retrieve Hospital B's patients or tasks.

2. **Outbound Priority Queue & Centralized Concurrency Governor (PRD Sec 10, 11)**:
   - **Central Concurrency Limit**: Enforced atomically via database transactions to prevent race conditions across distributed workers.
   - **Multi-Factor Priority Scoring**:
     $$PriorityScore = w_1 \cdot \text{Risk} + w_2 \cdot \text{DeadlinePressure} + w_3 \cdot \text{DischargeAge} + w_4 \cdot \text{CampaignWeight} + w_5 \cdot \text{Aging} - P_{retry}$$
   - **Non-Linear Deadline Ramp**: Approaching clinical cutoff (<4h) automatically boosts priority over newly admitted patients.
   - **Dead-Man Heartbeat Reaper**: Detects hung workers (>90s) and automatically reclaims outbound calling slots.
   - **Tiered Backoff Retries**: 15m $\rightarrow$ 60m $\rightarrow$ 240m with max retries transition to `MANUAL_FOLLOW_UP`.

3. **25-Patient Queue Simulation Studio (PRD Sec 12)**:
   - Live visual simulation featuring 25 mock patients with mixed clinical risks, deadlines, callbacks, and retries.
   - 3 visually animated concurrency calling slots showing atomic claim and release.
   - Discrete tick stepping, auto-run mode, and live scheduler telemetry console.

4. **Multi-Agent AI Safety & Conservative Consensus (PRD Sec 13, 14, 15, 16)**:
   - **Voice Intake Agent**: Protocol-driven conversational dialogue with identity verification and symptom screening.
   - **Clinical Triage Agent**: Extracts structured indicators into validated Pydantic schemas.
   - **Consensus Decision Engine**: Dual independent evaluators (Clinical Acuity Assessor + Protocol Compliance Assessor) plus an automated Rule Guardrail. Conservative policy: **If ANY evaluator detects a red flag, it forces human clinical escalation**.

5. **Clinical Reviewer Human-in-the-Loop Inbox (PRD Sec 21)**:
   - Review drawer showing patient summary, conversation transcript, cited hospital protocols, and multi-agent AI voting matrix.
   - Clinical action form allowing clinicians to resolve escalations and sync follow-up orders to the Mock EHR.

6. **Safety Evaluation & False-Negative Benchmark (PRD Sec 17)**:
   - 35 standardized test cases (Routine, Acute Red Flags, Ambiguous, Incomplete, Conflicting, and Prompt Injections).
   - Demonstrates **0.0% False-Negative Rate (FNR)**, 100% Sensitivity, and 100% Prompt Injection defense.

7. **Mock EHR Abstraction Layer (PRD Sec 6)**:
   - Extensible `EHRClient` interface with `MockEHRService` storing FHIR Communication, Observation, and Task resources.
   - Built-in fault injection (simulates 504 gateway timeouts).

---

## Evaluation Walkthrough Guide

| Step | Action in UI | Expected System Behavior |
| :--- | :--- | :--- |
| **1** | Open `http://localhost:8000` | Operations dashboard loads with Metro General Hospital pre-selected. Capacity meter shows active vs total slots. |
| **2** | Click **"Launch Call Simulator"** | Interactive phone modal opens. Agent greets patient. |
| **3** | Click preset **"CHF Red Flag (4 lb gain)"** | Patient says *"I gained 4 pounds and I can't breathe when lying down flat."* Agent detects emergency symptoms, initiates warm transfer, concludes call, executes dual-agent consensus, flags `URGENT`, and creates an open escalation. |
| **4** | Switch to **"Clinical Escalations"** tab | The new escalation appears in the queue. Click it to view patient details, cited AHA/ACC protocol rule, and multi-agent voting breakdown. |
| **5** | Submit Resolution | Select *"Urgent Clinic Triage Appointment Scheduled"*, enter clinical notes, click Resolve. Status updates to `RESOLVED` and follow-up order commits to Mock EHR. |
| **6** | Switch to **"Queue Simulator Studio"** | Click **"Step Tick"** or **"Auto-Run"**. Watch the 3 concurrency slots occupy, calls transition through states, retries back off, and telemetry stream in real time. |
| **7** | Switch to **"Safety Benchmark"** tab | Click **"Run Full Safety Benchmark"**. 35 cases are evaluated. Verify **0.0% False-Negative Rate (FNR)** and inspect the 2x2 confusion matrix. |
| **8** | Switch to **"EHR & System Health"** tab | Inspect synchronized FHIR Communication records, AI token latency, and tamper-evident audit logs. |

---

## Project Structure

```
AI_prof/
├── backend/
│   ├── app/
│   │   ├── api/             # REST endpoints (campaigns, queue, calls, escalations, ehr, safety)
│   │   ├── ai/              # Multi-agent AI: Intake, Triage, Consensus, Documentation, Tools
│   │   ├── ehr/             # EHR Abstraction interface & MockEHRService (FHIR models)
│   │   ├── models/          # Multi-tenant SQLAlchemy models & FHIR entities
│   │   ├── protocols/       # Hospital clinical protocols & tenant-aware store
│   │   ├── queue/           # Concurrency Governor, Prioritizer, Retry Policy, Reaper
│   │   ├── safety/          # 35-case safety evaluation dataset & benchmark runner
│   │   ├── schemas/         # Pydantic v2 validation models
│   │   ├── seeds/           # Multi-tenant seed data generator (250+ patients)
│   │   ├── config.py        # Settings & priorities
│   │   ├── database.py      # Async SQLite with WAL mode
│   │   └── main.py          # FastAPI application & static mount
│   ├── static/              # Pure HTML5, CSS3, and JavaScript frontend
│   │   ├── css/styles.css   # Dark slate clinical aesthetic & responsive styles
│   │   ├── js/api.js        # Vanilla API client
│   │   ├── js/app.js        # State management, simulator, and DOM rendering
│   │   └── index.html       # Single-page operations portal
│   ├── tests/               # Pytest suite (14 automated tests)
│   └── requirements.txt     # Python backend dependencies
├── docs/
│   ├── ARCHITECTURE.md      # Architecture diagrams & service boundaries
│   ├── QUEUE_DESIGN.md      # Queue state machine, priority formula & concurrency
│   ├── SAFETY_EVALUATION.md # Benchmark report & false-negative analysis
│   ├── AI_USAGE.md          # Multi-agent design, schemas & controlled tools
│   └── LIMITATIONS.md       # Prototype vs production roadmap
└── README.md
```

---

## License & Evaluation
Prepared for the **Full Stack AI Engineer / AI Systems Engineer** post-discharge outreach operational platform challenge.
