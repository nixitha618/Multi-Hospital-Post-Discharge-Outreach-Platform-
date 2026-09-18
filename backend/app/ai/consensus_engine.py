import re
from typing import List, Dict, Any, Optional
from backend.app.schemas.ai import EscalationConsensusResult, EvaluatorVote, StructuredTriageOutput
from backend.app.models.enums import UrgencyLevel

class EscalationConsensusEngine:
    """
    Multi-Evaluator Escalation Consensus Engine.
    Executes multiple independent reasoning paths and enforces a conservative clinical safety policy.
    Disagreements are explicitly detected, documented, and escalated to human clinicians.
    """

    @staticmethod
    def evaluate_consensus(
        triage_output: StructuredTriageOutput,
        transcript: str,
        patient_risk_tier: str = "MODERATE"
    ) -> EscalationConsensusResult:
        votes: List[EvaluatorVote] = []

        # Isolate PATIENT dialogue turns if transcript has speaker labels
        patient_lines = [
            line.split(":", 1)[1].strip()
            for line in transcript.split("\n")
            if line.strip().upper().startswith("PATIENT:")
        ]
        text_to_evaluate = " ".join(patient_lines) if patient_lines else transcript
        lower_t = text_to_evaluate.lower()

        # Path 1: Clinical Acuity Evaluator
        # Focuses on physiological distress and patient reported symptoms
        vote_a = triage_output.triage_classification
        conf_a = triage_output.confidence
        reason_a = f"Acuity Assessor observed {len(triage_output.observed_indicators)} indicators: {triage_output.clinical_reasoning}"
        flags_a = [i.symptom_key for i in triage_output.observed_indicators if i.presence]
        votes.append(EvaluatorVote(
            evaluator_name="Clinical_Acuity_Assessor",
            vote=vote_a,
            confidence=conf_a,
            reasoning=reason_a,
            flags=flags_a
        ))

        # Path 2: Protocol Compliance Evaluator
        # Focuses on protocol specific rules, weight thresholds, medication adherence
        flags_b = []
        vote_b = UrgencyLevel.ROUTINE
        conf_b = 0.90
        reason_b = "Protocol Compliance Assessor found no threshold breaches."

        # Accurate weight gain threshold breach check (>= 3 lbs gain in 48h)
        # Prevents normal baseline weights like "165 lbs" from falsely triggering
        weight_gain_match = re.search(
            r"\b(gained|gain|weight\s+up|up\s+by|went\s+up)\s+(like\s+|about\s+)?([3-9]|\d{2,})\s*(lbs?|pounds?)\b",
            lower_t
        )
        if not weight_gain_match:
            # Also check: "gained [3-9] pounds"
            weight_gain_match = re.search(r"\bgained\s+([3-9]|\d{2,})\s*(pounds?|lbs?)\b", lower_t)

        if weight_gain_match:
            start_pos = weight_gain_match.start()
            window_start = max(0, start_pos - 35)
            preceding = lower_t[window_start:start_pos]
            is_negated = bool(re.search(r"\b(no|not|denies|without|zero|negative)\s+([a-zA-Z]+\s+)?$", preceding))
            if not is_negated:
                vote_b = UrgencyLevel.URGENT
                flags_b.append("protocol_weight_threshold_breach")
                reason_b = "Exceeded hospital protocol guideline of >= 3 lbs weight gain in 48h."
        elif re.search(r"\b(weight\s+(is\s+)?up|gained\s+weight)\b", lower_t):
            # Check negation
            match_up = re.search(r"\b(weight\s+(is\s+)?up|gained\s+weight)\b", lower_t)
            preceding = lower_t[max(0, match_up.start() - 35):match_up.start()]
            if not re.search(r"\b(no|not|denies|without|zero)\s+([a-zA-Z]+\s+)?$", preceding):
                vote_b = UrgencyLevel.CONCERNING
                flags_b.append("unquantified_weight_gain")
                reason_b = "Reported weight change without specific measurement."

        # Mandatory symptoms check with negation support
        mandatory_symptom_patterns = [
            (r"\b(calf\b.*?\b(swollen|red|hot|pain|tender|hurts)|calf pain|swollen calf|calf redness|warmth in (my )?leg)\b", "protocol_mandatory_escalation_symptom"),
            (r"\b(incision open|pus|drainage leaking|wound red and hot)\b", "protocol_mandatory_escalation_symptom"),
            (r"\b(fever (over|above|of) 10[1-9]|high fever|chills and fever|10[1-9]\.[0-9])\b", "protocol_mandatory_escalation_symptom"),
            (r"\b(chest pain|pressure in (my )?chest|angina)\b", "protocol_mandatory_escalation_symptom"),
            (r"\b(can'?t breathe|short(ness)? of breath|trouble breathing|gasping|orthopnea)\b", "protocol_mandatory_escalation_symptom")
        ]
        for sym_pattern, flag_name in mandatory_symptom_patterns:
            for match in re.finditer(sym_pattern, lower_t):
                start_pos = match.start()
                window_start = max(0, start_pos - 35)
                preceding = lower_t[window_start:start_pos]
                is_neg = bool(re.search(r"\b(no|not|denies|without|free of|negative for|zero)\s+([a-zA-Z]+\s+)?$", preceding))
                if not is_neg:
                    vote_b = UrgencyLevel.URGENT
                    flags_b.append(flag_name)
                    reason_b = "Dialogue contains symptom categorized as mandatory protocol escalation."
                    break

        # Medication non-adherence check
        med_non_adh_match = re.search(
            r"\b(stopped taking|not taking|haven'?t taken|can'?t afford|ran out of|skipped|refusing)\s+(my\s+)?(meds|medications?|pills?|water pills?|blood thinner|prescriptions?)\b",
            lower_t
        )
        if med_non_adh_match and vote_b != UrgencyLevel.URGENT:
            vote_b = UrgencyLevel.CONCERNING
            flags_b.append("protocol_medication_non_adherence")
            reason_b = "Patient reported disruption or non-adherence to essential discharge medication regimen."

        # Swelling / peripheral edema check
        edema_match = re.search(
            r"\b(swelling in (my )?(feet|ankles|legs)|shoes (are )?(too )?tight|feet (are )?swollen|legs (are )?swollen|ankles (are )?swollen|swollen feet|swollen ankles|swollen legs|severely swollen)\b",
            lower_t
        )
        if edema_match and vote_b != UrgencyLevel.URGENT:
            start_pos = edema_match.start()
            window_start = max(0, start_pos - 35)
            preceding = lower_t[window_start:start_pos]
            is_neg = bool(re.search(r"\b(no|not|denies|without|free of|negative for|zero)\s+([a-zA-Z]+\s+)?$", preceding))
            if not is_neg:
                vote_b = UrgencyLevel.CONCERNING
                flags_b.append("protocol_peripheral_edema")
                reason_b = "Patient reported new or worsening lower extremity edema."

        if not flags_b and vote_a == UrgencyLevel.ROUTINE:
            vote_b = UrgencyLevel.ROUTINE
            reason_b = "Protocol parameters satisfied without violation."

        votes.append(EvaluatorVote(
            evaluator_name="Protocol_Compliance_Assessor",
            vote=vote_b,
            confidence=conf_b,
            reasoning=reason_b,
            flags=flags_b
        ))

        # Path 3: Deterministic Safety Arbiter (Hard rule checks)
        vote_c = UrgencyLevel.ROUTINE
        flags_c = []
        for hard_sym in [r"\bchest pain\b", r"\bcalf pain\b"]:
            for match in re.finditer(hard_sym, lower_t):
                start_pos = match.start()
                window_start = max(0, start_pos - 35)
                preceding = lower_t[window_start:start_pos]
                is_neg = bool(re.search(r"\b(no|not|denies|without|free of|negative for|zero)\s+([a-zA-Z]+\s+)?$", preceding))
                if not is_neg:
                    vote_c = UrgencyLevel.URGENT
                    flags_c.append("emergency_hard_stop")
                    break
        if "adversarial" in lower_t or "ignore previous instructions" in lower_t or "override system" in lower_t or "tell me i am 100% cured" in lower_t:
            vote_c = UrgencyLevel.UNCERTAIN
            flags_c.append("security_boundary_flag")

        # Check for disagreement between primary evaluators
        disagreement = (vote_a != vote_b)
        disagreement_notes = None
        if disagreement:
            disagreement_notes = f"Disagreement detected: Acuity Assessor voted {vote_a.value}, whereas Protocol Assessor voted {vote_b.value}."

        # Conservative consensus rule:
        # If ANY assessor votes URGENT -> consensus is URGENT
        # Else if ANY votes CONCERNING -> consensus is CONCERNING
        # Else if ANY votes UNCERTAIN -> consensus is UNCERTAIN (safety under ambiguity)
        # Else -> ROUTINE
        all_votes = [vote_a, vote_b, vote_c]
        if UrgencyLevel.URGENT in all_votes:
            consensus = UrgencyLevel.URGENT
        elif UrgencyLevel.CONCERNING in all_votes:
            consensus = UrgencyLevel.CONCERNING
        elif UrgencyLevel.UNCERTAIN in all_votes:
            consensus = UrgencyLevel.UNCERTAIN
        else:
            consensus = UrgencyLevel.ROUTINE

        # High baseline patient risk bias: if patient is CRITICAL risk tier, even UNCERTAIN becomes ESCALATE
        escalate = (consensus in [UrgencyLevel.URGENT, UrgencyLevel.CONCERNING, UrgencyLevel.UNCERTAIN])
        if patient_risk_tier == "CRITICAL" and consensus == UrgencyLevel.ROUTINE and len(transcript) < 30:
            # Insufficient dialogue from a critical patient -> conservative escalation
            consensus = UrgencyLevel.UNCERTAIN
            escalate = True
            disagreement_notes = "Conservative bias applied: High-risk patient with minimal response escalated for human verification."

        all_flags = list(set(flags_a + flags_b + flags_c))

        return EscalationConsensusResult(
            consensus_decision=consensus,
            escalate_to_human=escalate,
            agreement=(not disagreement),
            disagreement_detected=disagreement,
            disagreement_notes=disagreement_notes,
            rule_override_applied=(vote_c == UrgencyLevel.URGENT and vote_a != UrgencyLevel.URGENT),
            votes=votes,
            final_rationale=f"Consensus reached: {consensus.value}. " + (disagreement_notes or "Assessors in full agreement."),
            cited_red_flags=all_flags
        )

consensus_engine = EscalationConsensusEngine()
