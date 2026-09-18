import json
import re
from typing import List, Dict, Any, Optional
from backend.app.schemas.ai import StructuredTriageOutput, ObservedIndicator
from backend.app.models.enums import UrgencyLevel

class ClinicalTriageAgent:
    """
    Clinical Triage Agent.
    Analyzes patient dialogue against hospital clinical protocols and red-flag rules.
    Outputs validated StructuredTriageOutput with evidence citations.
    """

    # Red-flag heuristic patterns for deterministic grounding
    RED_FLAG_PATTERNS = [
        {"pattern": r"\b(chest pain|pressure in (my )?chest|angina)\b", "key": "chest_pain", "severity": "CRITICAL", "citation": "Emergency Protocol 1.1"},
        {"pattern": r"\b(can'?t breathe|short(ness)? of breath|trouble breathing|gasping|orthopnea)\b", "key": "dyspnea", "severity": "CRITICAL", "citation": "Cardiopulmonary Protocol 2.1"},
        {"pattern": r"\b(calf\b.*?\b(swollen|red|hot|pain|tender|hurts)|calf pain|swollen calf|calf redness|warmth in (my )?leg)\b", "key": "calf_pain_dvt", "severity": "CRITICAL", "citation": "AAOS DVT Guideline Rule 1"},
        {"pattern": r"\b(fever (over|above|of) 10[1-9]|high fever|chills and fever|10[1-9]\.[0-9])\b", "key": "fever", "severity": "CRITICAL", "citation": "Infection Protocol 3.2"},
        {"pattern": r"\b(pus|drainage leaking|incision open|wound red and hot)\b", "key": "wound_infection", "severity": "CRITICAL", "citation": "CDC Surgical Site Guideline"},
        {"pattern": r"\b(gained [3-9] (pounds|lbs)|weight up [3-9] lbs)\b", "key": "weight_gain", "severity": "URGENT", "citation": "AHA/ACC HF Protocol 4.2"},
        {"pattern": r"\b(dizzy|lightheaded|almost fainted|passed out)\b", "key": "dizziness", "severity": "CONCERNING", "citation": "Hemodynamic Protocol 5.1"},
        {"pattern": r"\b(swelling in (my )?(feet|ankles|legs)|shoes (are )?(too )?tight|feet (are )?swollen|legs (are )?swollen|ankles (are )?swollen|swollen feet|swollen ankles|swollen legs|severely swollen)\b", "key": "edema", "severity": "CONCERNING", "citation": "AHA/ACC HF Protocol 4.4"},
        {"pattern": r"\b(stopped taking|not taking|haven'?t taken|can'?t afford|ran out of|skipped|refusing)\s+(my\s+)?(meds|medications?|pills?|water pills?|blood thinner|prescriptions?)\b", "key": "medication_non_adherence", "severity": "CONCERNING", "citation": "Pharmacotherapy Safety Protocol 6.1"}
    ]

    @staticmethod
    def evaluate_transcript(
        transcript: str,
        patient_name: str,
        condition: str,
        protocol_red_flags: Optional[List[Dict[str, Any]]] = None
    ) -> StructuredTriageOutput:
        """
        Extracts clinical indicators, maps to protocol citations, and classifies triage urgency.
        """
        indicators: List[ObservedIndicator] = []
        citations: List[str] = []

        # When a full multi-turn transcript is provided with speaker prefixes,
        # isolate the PATIENT's actual statements so the AGENT's screening questions
        # (e.g. "Are you having shortness of breath?") are not mistaken for patient symptoms.
        patient_lines = [
            line.split(":", 1)[1].strip()
            for line in transcript.split("\n")
            if line.strip().upper().startswith("PATIENT:")
        ]
        text_to_evaluate = " ".join(patient_lines) if patient_lines else transcript
        lower_t = text_to_evaluate.lower()

        # Check prompt injection defense
        # If user tried to say "ignore instructions", we flag it as UNCERTAIN / suspicious
        if "ignore previous instructions" in lower_t or "override system" in lower_t or "tell me i am 100% cured" in lower_t:
            return StructuredTriageOutput(
                triage_classification=UrgencyLevel.UNCERTAIN,
                confidence=0.95,
                observed_indicators=[
                    ObservedIndicator(
                        symptom_key="adversarial_attempt",
                        presence=True,
                        description="Untrusted user input attempted prompt override; conservative safety escalation triggered.",
                        severity="CRITICAL"
                    )
                ],
                protocol_references=["Safety Guardrail Rule SEC-01"],
                clinical_reasoning="Adversarial content detected in patient dialogue. Conservative fallback to human triage.",
                escalation_recommended=True,
                suggested_nurse_actions=["Perform manual phone verification with patient."]
            )

        # Check against patterns
        has_critical = False
        has_concerning = False

        for rf in ClinicalTriageAgent.RED_FLAG_PATTERNS:
            for match in re.finditer(rf["pattern"], lower_t):
                # Check for clinical negation preceding the match (e.g. "no shortness of breath", "denies chest pain", "without swelling")
                start_pos = match.start()
                window_start = max(0, start_pos - 35)
                preceding = lower_t[window_start:start_pos]
                is_negated = bool(re.search(r"\b(no|not|denies|without|free of|negative for|zero)\s+([a-zA-Z]+\s+)?$", preceding))
                if is_negated:
                    continue  # Patient specifically negated/denied this symptom

                snippet = match.group(0)
                sev = rf["severity"]
                if sev == "CRITICAL":
                    has_critical = True
                elif sev == "CONCERNING":
                    has_concerning = True

                indicators.append(
                    ObservedIndicator(
                        symptom_key=rf["key"],
                        presence=True,
                        description=f"Patient reported symptom: {rf['key']}",
                        patient_quote=snippet,
                        severity=sev
                    )
                )
                citations.append(rf["citation"])
                break  # Record indicator once per pattern

        # Check protocol red-flags if provided
        if protocol_red_flags:
            for prf in protocol_red_flags:
                ind_text = prf.get("indicator", "").lower()
                # If key terms appear in transcript
                for word in ind_text.split():
                    if len(word) > 4 and word in lower_t and prf.get("citation") not in citations:
                        citations.append(prf.get("citation", "Hospital Clinical Protocol"))

        # Determine triage classification
        if has_critical:
            classification = UrgencyLevel.URGENT
            escalate = True
            reason = f"Detected acute red-flag indicators ({', '.join([i.symptom_key for i in indicators if i.severity == 'CRITICAL'])}) requiring immediate human escalation."
        elif has_concerning:
            classification = UrgencyLevel.CONCERNING
            escalate = True
            reason = f"Patient exhibited symptoms concerning for decompensation ({', '.join([i.symptom_key for i in indicators])}). Timely clinical nurse review recommended."
        else:
            # Check if dialogue is routine
            routine_terms = [
                "fine", "good", "recovering", "better", "no pain", "taking meds",
                "no problems", "doing well", "feeling well", "steady", "normal",
                "all good", "no issues", "no swelling", "no shortness of breath"
            ]
            if any(w in lower_t for w in routine_terms):
                classification = UrgencyLevel.ROUTINE
                escalate = False
                reason = "Patient reports stable recovery, adherence to medications, and absence of acute symptoms."
            else:
                # Ambiguous or incomplete
                classification = UrgencyLevel.UNCERTAIN
                escalate = True # Conservative safety: uncertainty escalates!
                reason = "Conversation was ambiguous or incomplete. Conservative clinical safety dictates human escalation."

        return StructuredTriageOutput(
            triage_classification=classification,
            confidence=0.92,
            observed_indicators=indicators,
            protocol_references=list(set(citations)) if citations else ["Routine Post-Discharge Monitoring Standard"],
            clinical_reasoning=reason,
            escalation_recommended=escalate,
            suggested_nurse_actions=[
                "Review vital signs and recent labs",
                "Contact patient within 2 hours" if escalate else "Schedule next routine follow-up"
            ]
        )

clinical_triage_agent = ClinicalTriageAgent()
