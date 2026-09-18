from typing import List, Dict, Any

DEFAULT_PROTOCOLS: List[Dict[str, Any]] = [
    {
        "code": "PROTO-CHF-01",
        "name": "Congestive Heart Failure Post-Discharge Outreach Protocol",
        "target_condition": "CHF",
        "version": "2.1",
        "description": "Evidence-based post-discharge monitoring protocol for heart failure patients within 48-72h of discharge.",
        "red_flags": [
            {
                "indicator": "Weight gain >= 3 lbs in 2 days or >= 5 lbs in a week",
                "severity": "URGENT",
                "action_required": "Escalate to HF Nurse Navigator immediately; assess for diuretic dose adjustment",
                "citation": "AHA/ACC HF Guidelines Sec 4.2"
            },
            {
                "indicator": "Worsening shortness of breath at rest or when lying flat (orthopnea)",
                "severity": "URGENT",
                "action_required": "Immediate escalation; urgent clinic visit or ED evaluation if accompanied by chest pain",
                "citation": "AHA/ACC HF Guidelines Sec 4.3"
            },
            {
                "indicator": "New or worsening bilateral swelling in lower legs, ankles, or abdomen",
                "severity": "CONCERNING",
                "action_required": "Escalate to clinic triage nurse within 4 hours",
                "citation": "AHA/ACC HF Guidelines Sec 4.4"
            },
            {
                "indicator": "Dizziness, lightheadedness, or feeling faint upon standing",
                "severity": "CONCERNING",
                "action_required": "Evaluate blood pressure meds and hydration; escalate to nurse",
                "citation": "AHA/ACC HF Guidelines Sec 5.1"
            }
        ],
        "questions": [
            {
                "sequence_order": 1,
                "category": "greeting",
                "question_text": "Hello, I am calling from {hospital_name} post-discharge care team to see how you are feeling since returning home. Do you have a few minutes to talk about your recovery?",
                "expected_observation_key": "patient_available",
                "guidance": "Confirm identity and verify patient is safe and comfortable to talk."
            },
            {
                "sequence_order": 2,
                "category": "symptom",
                "question_text": "Have you been checking your weight every morning, and have you noticed any sudden weight gain, like 3 pounds or more in the last couple of days?",
                "expected_observation_key": "weight_gain_lbs",
                "guidance": "Fluid retention is the primary warning sign for heart failure decompensation."
            },
            {
                "sequence_order": 3,
                "category": "symptom",
                "question_text": "How is your breathing? Are you experiencing any shortness of breath, especially when lying down or with light activity?",
                "expected_observation_key": "shortness_of_breath",
                "guidance": "Distinguish between baseline dyspnea and acute worsening."
            },
            {
                "sequence_order": 4,
                "category": "symptom",
                "question_text": "Have you noticed any new or increased swelling in your legs, ankles, or feet?",
                "expected_observation_key": "peripheral_edema",
                "guidance": "Check for pitting edema or shoes feeling tight."
            },
            {
                "sequence_order": 5,
                "category": "medication",
                "question_text": "Have you been able to pick up and take your prescribed water pills and heart medications as directed?",
                "expected_observation_key": "medication_adherence",
                "guidance": "Verify adherence and ask about any adverse effects."
            },
            {
                "sequence_order": 6,
                "category": "follow_up",
                "question_text": "Do you have an upcoming appointment scheduled with your cardiologist or primary care provider?",
                "expected_observation_key": "followup_appointment_scheduled",
                "guidance": "Ensure patient has follow-up within 7-14 days."
            }
        ]
    },
    {
        "code": "PROTO-TKA-02",
        "name": "Total Knee & Hip Arthroplasty Recovery Protocol",
        "target_condition": "ORTHOPEDICS",
        "version": "1.8",
        "description": "Post-operative monitoring for joint replacement patients focusing on DVT prophylaxis, surgical site infection, and pain control.",
        "red_flags": [
            {
                "indicator": "Unilateral calf pain, tenderness, redness, or localized warmth (DVT suspect)",
                "severity": "URGENT",
                "action_required": "Immediate escalation for emergency venous duplex ultrasound",
                "citation": "AAOS Post-Arthroplasty DVT Safety Standard Rule 1"
            },
            {
                "indicator": "Fever > 101.0°F (38.3°C) or purulent wound drainage / active spreading erythema",
                "severity": "URGENT",
                "action_required": "Escalate to orthopedic on-call PA/surgeon immediately",
                "citation": "CDC Surgical Site Infection Protocol 2024"
            },
            {
                "indicator": "Severe uncontrolled pain not relieved by prescribed post-op analgesic regimen",
                "severity": "CONCERNING",
                "action_required": "Clinical reviewer review for medication adjustment",
                "citation": "AAOS Pain Management Guide"
            }
        ],
        "questions": [
            {
                "sequence_order": 1,
                "category": "greeting",
                "question_text": "Hello, this is {hospital_name} orthopedic care outreach. We are checking in on your knee/hip recovery. How is your pain level today on a scale from 0 to 10?",
                "expected_observation_key": "pain_scale_score",
                "guidance": "Pain score >= 8 warrants deeper assessment."
            },
            {
                "sequence_order": 2,
                "category": "symptom",
                "question_text": "Have you noticed any new pain, swelling, warmth, or redness in your calf or lower leg?",
                "expected_observation_key": "calf_pain_dvt",
                "guidance": "Critical screen for deep vein thrombosis."
            },
            {
                "sequence_order": 3,
                "category": "symptom",
                "question_text": "How does your surgical incision look? Is there any bleeding, unusual drainage, odor, or spreading redness around the incision?",
                "expected_observation_key": "surgical_site_drainage",
                "guidance": "Check for signs of surgical site infection."
            },
            {
                "sequence_order": 4,
                "category": "medication",
                "question_text": "Are you taking your blood thinner medication as prescribed to help prevent blood clots?",
                "expected_observation_key": "anticoagulant_adherence",
                "guidance": "Crucial for post-op safety."
            }
        ]
    },
    {
        "code": "PROTO-SEP-03",
        "name": "Post-Sepsis Care & Recovery Protocol",
        "target_condition": "SEPSIS",
        "version": "1.4",
        "description": "Post-discharge monitoring for sepsis survivors to prevent recurrence, post-sepsis syndrome, and secondary infection.",
        "red_flags": [
            {
                "indicator": "Fever > 101.5°F or hypothermia < 96.0°F",
                "severity": "URGENT",
                "action_required": "Immediate escalation; sepsis recurrence protocol",
                "citation": "Surviving Sepsis Campaign Post-ICU Care"
            },
            {
                "indicator": "New confusion, extreme lethargy, or slurred speech",
                "severity": "URGENT",
                "action_required": "Emergency evaluation recommended; call 911 / ED",
                "citation": "Surviving Sepsis Campaign Sec 7"
            },
            {
                "indicator": "Rapid heart rate (>100 bpm) or fast breathing at rest",
                "severity": "URGENT",
                "action_required": "Immediate clinical escalation",
                "citation": "Surviving Sepsis Campaign Sec 7.2"
            }
        ],
        "questions": [
            {
                "sequence_order": 1,
                "category": "greeting",
                "question_text": "Hello, this is {hospital_name} specialized follow-up team checking in on your recovery after your recent treatment for infection. How are your energy levels and overall feeling today?",
                "expected_observation_key": "general_status",
                "guidance": "Assess mental clarity and responsiveness."
            },
            {
                "sequence_order": 2,
                "category": "symptom",
                "question_text": "Have you had any chills, shaking, or measured a fever above 101 degrees?",
                "expected_observation_key": "fever_temperature",
                "guidance": "Screen for reinfection."
            },
            {
                "sequence_order": 3,
                "category": "symptom",
                "question_text": "Are you feeling any racing heartbeat, trouble catching your breath, or unusual dizziness?",
                "expected_observation_key": "vital_instability",
                "guidance": "Screen for systemic hypoperfusion."
            },
            {
                "sequence_order": 4,
                "category": "medication",
                "question_text": "Have you finished all your prescribed antibiotics, or are you still taking them on schedule?",
                "expected_observation_key": "antibiotic_completion",
                "guidance": "Check course completion."
            }
        ]
    }
]
