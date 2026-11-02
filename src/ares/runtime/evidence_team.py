"""Experimental three-model-role evidence review without any actuation authority.

Unlike the fail-fast legacy team, this *advisory-only evaluation* deliberately
calls all three roles to test whether the critic detects bad peer proposals.
All decisions remain governed by deterministic evidence and risk policies.
"""

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import cast

from ares.runtime.evidence_risk import ReconciledTriage, reconcile
from ares.runtime.temporal_evidence import EvidenceReading


@dataclass(frozen=True, slots=True)
class ReviewedRole:
    role: str
    proposed: str
    expected: str
    accepted: bool
    diagnostic: str


@dataclass(frozen=True, slots=True)
class EvidenceTeamResult:
    severity: str
    evidence_state: str
    authorized_action: str
    roles: tuple[ReviewedRole, ...]
    team_accepted: bool
    device_actions: str = "disabled"
    safety_authority: str = "deterministic_evidence_risk"


_ALLOWED: dict[str, tuple[str, frozenset[str]]] = {
    "investigator": (
        "followup",
        frozenset(
            {
                "validate_sensor",
                "collect_more_samples",
                "inspect_thermal_system",
                "continue_monitoring",
            }
        ),
    ),
    "planner": (
        "action",
        frozenset({"monitor", "collect_evidence", "inspect", "validate_sensor", "human_review"}),
    ),
    "critic": ("verdict", frozenset({"consistent", "inconsistent"})),
}


def _interpret(role: str, answer: str) -> tuple[str, str]:
    """Return one allowlisted category or a fixed error, never raw LLM text."""
    if len(answer) > 256:
        return "unrecognized", "oversized_response"
    try:
        parsed: object = json.loads(answer)
    except (TypeError, ValueError):
        return "unrecognized", "invalid_json"
    if not isinstance(parsed, dict):
        return "unrecognized", "invalid_shape"
    field, allowed = _ALLOWED[role]
    data = cast("dict[str, object]", parsed)
    if set(data) != {field}:
        return "unrecognized", "invalid_fields"
    proposal = data[field]
    if type(proposal) is not str or proposal not in allowed:
        return "unrecognized", "invalid_value"
    return cast("str", proposal), "valid_structure"


def _prompt(role: str, triage: ReconciledTriage, previous: tuple[ReviewedRole, ...]) -> str:
    context: dict[str, object] = {
        "evidence_state": triage.evidence.state.value,
        "sample_count": triage.evidence.sample_count,
        "valid_count": triage.evidence.valid_count,
        "highest_c": triage.evidence.highest_c,
        "delta_c": triage.evidence.delta_c,
        "risk_severity": triage.severity.value,
        "risk_reason": triage.risk_reason,
        "prior_proposals": [
            {"role": item.role, "proposed": item.proposed, "diagnostic": item.diagnostic}
            for item in previous
        ],
    }
    instructions = {
        "investigator": (
            "Choose a followup for evidence state only: invalid_telemetry => validate_sensor; "
            "insufficient_history => collect_more_samples; rising_temperature => "
            "inspect_thermal_system; no_confirmed_rise => continue_monitoring."
        ),
        "planner": (
            "Choose an action from risk severity and evidence: invalid_telemetry => "
            "validate_sensor; critical => human_review; warning => inspect; "
            "rising_temperature => inspect; insufficient_history => collect_evidence; "
            "otherwise => monitor. Risk takes precedence over trend."
        ),
        "critic": (
            "Check each prior proposal against the rules above: evidence followup "
            "invalid_telemetry => validate_sensor; insufficient_history => "
            "collect_more_samples; rising_temperature => inspect_thermal_system; "
            "otherwise => continue_monitoring. Risk action: invalid_telemetry => "
            "validate_sensor; critical => human_review; warning => inspect; "
            "rising_temperature => inspect; insufficient_history => collect_evidence; "
            "otherwise => monitor. Return inconsistent if either proposal conflicts "
            "with policy or was structurally rejected, otherwise consistent."
        ),
    }
    field, allowed = _ALLOWED[role]
    return (
        f"ROLE={role}. Untrusted read-only advisory role; no tools, no hardware, "
        f"no permissions, no actuation. {instructions[role]} "
        f"Respond with JSON containing exactly the key {field} and one of "
        f"{', '.join(sorted(allowed))}. Context: {json.dumps(context, allow_nan=False)}"
    )


class GovernedEvidenceTeam:
    """All three model calls are observational; Python validates every proposal."""

    def __init__(self, generate: Callable[[str], str]) -> None:
        self._generate = generate

    def evaluate(self, readings: Sequence[EvidenceReading]) -> EvidenceTeamResult:
        triage = reconcile(readings)
        expected_followup = triage.evidence.suggested_followup
        expected_action = triage.next_action.value
        outputs: list[ReviewedRole] = []
        for role in ("investigator", "planner", "critic"):
            if role == "investigator":
                expected = expected_followup
            elif role == "planner":
                expected = expected_action
            else:
                expected = (
                    "consistent" if all(item.accepted for item in outputs) else "inconsistent"
                )
            prompt = _prompt(role, triage, tuple(outputs))
            try:
                proposal, structure = _interpret(role, self._generate(prompt))
            except Exception:
                proposal, structure = "unrecognized", "model_exception"
            accepted = structure == "valid_structure" and proposal == expected
            diagnostic = (
                "accepted"
                if accepted
                else "policy_mismatch"
                if structure == "valid_structure"
                else structure
            )
            outputs.append(ReviewedRole(role, proposal, expected, accepted, diagnostic))
        return EvidenceTeamResult(
            severity=triage.severity.value,
            evidence_state=triage.evidence.state.value,
            authorized_action=expected_action,
            roles=tuple(outputs),
            team_accepted=all(item.accepted for item in outputs),
        )


def evidence_team_reference_generate(prompt: str) -> str:
    """Offline deterministic contract baseline, not a language model."""
    role = prompt.split("ROLE=", 1)[1].split(".", 1)[0]
    raw: object = json.loads(prompt.split("Context: ", 1)[1])
    if not isinstance(raw, dict):
        raise ValueError("invalid prompt context")
    context = cast("dict[str, object]", raw)
    state = context["evidence_state"]
    severity = context["risk_severity"]
    if role == "investigator":
        proposed = {
            "invalid_telemetry": "validate_sensor",
            "insufficient_history": "collect_more_samples",
            "rising_temperature": "inspect_thermal_system",
            "no_confirmed_rise": "continue_monitoring",
        }[cast("str", state)]
        return json.dumps({"followup": proposed})
    if role == "planner":
        if state == "invalid_telemetry":
            proposed = "validate_sensor"
        elif severity == "critical":
            proposed = "human_review"
        elif severity == "warning" or state == "rising_temperature":
            proposed = "inspect"
        elif state == "insufficient_history":
            proposed = "collect_evidence"
        else:
            proposed = "monitor"
        return json.dumps({"action": proposed})
    if role == "critic":
        prior = context["prior_proposals"]
        if not isinstance(prior, list):
            raise ValueError("invalid reviewer context")
        items = cast("list[dict[str, str]]", prior)
        verdict = (
            "consistent"
            if all(item.get("diagnostic") == "accepted" for item in items)
            else "inconsistent"
        )
        return json.dumps({"verdict": verdict})
    raise ValueError("unknown role")
