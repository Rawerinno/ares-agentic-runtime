"""Three bounded LLM agent roles governed by deterministic incident policy.

These are three separate model invocations, sequential on one local model.
No model can call tools, change severity, operate hardware, or grant approval.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING, cast

from ares.evaluation.ollama_capability_boundary import Generate
from ares.supervisor import Assessment, Severity

if TYPE_CHECKING:
    from ares.runtime.multi_agent_mvp import RoleHandoff


@dataclass(frozen=True, slots=True)
class TeamOutcome:
    status: str
    handoffs: tuple[RoleHandoff, ...]
    calls: int
    error_code: str | None


def _mismatch_reason(actual: object, expected: dict[str, str]) -> str:
    """Return only a fixed diagnostic code, never raw model-generated text."""
    if not isinstance(actual, dict):
        return "invalid_shape"
    fields = cast("dict[object, object]", actual)
    if set(fields) != set(expected):
        return "invalid_fields"
    if any(type(value) is not str for value in fields.values()):
        return "invalid_types"
    if "severity" in expected and fields["severity"] != expected["severity"]:
        return "severity_mismatch"
    role_field = next(field for field in expected if field != "severity")
    if fields[role_field] != expected[role_field]:
        return f"{role_field}_mismatch"
    return "none"


class GovernedThreeAgentTeam:
    """Investigator, planner, critic; each provides bounded advisory enums."""

    def __init__(
        self, generate: Generate, *, identity: str = "three-role-v1", role_only: bool = False
    ) -> None:
        if not identity.strip() or len(identity) > 120:
            raise ValueError("team identity must be 1..120 nonblank characters")
        self._generate = generate
        self.identity = identity
        self.role_only = role_only

    def evaluate(self, assessment: Assessment) -> TeamOutcome:
        from ares.runtime.multi_agent_mvp import RoleHandoff

        severity = assessment.severity.value
        healthy = assessment.snapshot.healthy
        hypothesis = (
            "sensor_fault"
            if not healthy or not isfinite(assessment.snapshot.temperature_c)
            else "stable"
            if assessment.severity is Severity.NORMAL
            else "thermal_load"
        )
        planned = {
            Severity.NORMAL: "monitor",
            Severity.WARNING: "inspect",
            Severity.CRITICAL: "human_review",
        }[assessment.severity]
        descriptions = (
            (
                "investigator",
                {"hypothesis": hypothesis, "severity": severity},
                "Identify a bounded hypothesis from authoritative telemetry",
            ),
            (
                "planner",
                {"plan": planned, "severity": severity},
                "Propose a non-executable response consistent with the severity",
            ),
            (
                "critic",
                {"verdict": "consistent", "severity": severity},
                "Independently check prior agent outputs against trusted severity",
            ),
        )
        rules = {
            "investigator": (
                "For healthy finite telemetry: normal severity => stable; "
                "warning or critical severity => thermal_load. "
                "Unhealthy or missing/non-finite sensor => sensor_fault. "
                "Output exactly hypothesis and severity."
            ),
            "planner": (
                "Map authoritative severity to advisory plan: "
                "normal => monitor; warning => inspect; critical => human_review. "
                "Do not substitute request_review, investigate, or other words. "
                "Output exactly plan and severity."
            ),
            "critic": (
                "Prior roles shown here have already been validated by ARES. "
                "Return verdict=consistent when they agree with authoritative severity. "
                "Return verdict=inconsistent only for a genuine contradiction. "
                "Output exactly verdict and severity."
            ),
        }
        handoffs: list[RoleHandoff] = []
        calls = 0
        for role, expected_full, instruction in descriptions:
            expected = (
                {key: value for key, value in expected_full.items() if key != "severity"}
                if self.role_only
                else expected_full
            )
            trusted = {
                "severity": severity,
                "temperature_c": (
                    assessment.snapshot.temperature_c
                    if isfinite(assessment.snapshot.temperature_c)
                    else None
                ),
                "healthy": healthy,
                "validated_prior_roles": [
                    {"role": item.role, "finding": item.finding} for item in handoffs
                ],
            }
            question = (
                f"ROLE={role}. {instruction}. {rules[role]} "
                "You have NO tool permissions and must not change severity. "
                "Respond with exactly one JSON object containing "
                + ("ONLY the role-specific field, no severity field. " if self.role_only else "the role-specific field AND severity. ")
                + "No Markdown or prose. "
                f"Trusted context: {json.dumps(trusted, allow_nan=False)}."
            )
            calls += 1
            try:
                answer = self._generate(question)
            except Exception:
                handoffs.append(
                    RoleHandoff(role, "Rejected: model_exception", "Deterministic fallback")
                )
                return TeamOutcome("rejected", tuple(handoffs), calls, "model_exception")
            reason = "invalid_json"
            try:
                if len(answer) > 256:
                    reason = "oversized_response"
                else:
                    parsed: object = json.loads(answer)
                    reason = _mismatch_reason(parsed, expected)
            except (ValueError, TypeError):
                reason = "invalid_json"
            if reason != "none":
                handoffs.append(
                    RoleHandoff(
                        role,
                        f"Rejected: policy_mismatch:{reason}",
                        "Deterministic fallback",
                    )
                )
                return TeamOutcome("rejected", tuple(handoffs), calls, "policy_mismatch")
            handoffs.append(
                RoleHandoff(
                    role,
                    f"Validated: {', '.join(f'{key}={value}' for key, value in expected.items())}",
                    "Advisory only; no execution authority",
                )
            )
        return TeamOutcome("accepted", tuple(handoffs), calls, None)


def reference_generate(question: str) -> str:
    """Deterministic offline three-role baseline (not a language model)."""
    role = question.split("ROLE=", 1)[1].split(".", 1)[0]
    fragment = question.split("Trusted context: ", 1)[1].removesuffix(".")
    raw: object = json.loads(fragment)
    if not isinstance(raw, dict):
        raise ValueError("invalid reference context")
    context = cast("dict[str, object]", raw)
    severity = context.get("severity")
    if severity not in ("normal", "warning", "critical"):
        raise ValueError("invalid reference severity")
    role_only = "ONLY the role-specific field, no severity field." in question
    if role == "investigator":
        hypothesis = (
            "sensor_fault"
            if context.get("healthy") is not True or context.get("temperature_c") is None
            else "stable"
            if severity == "normal"
            else "thermal_load"
        )
        result = {"hypothesis": hypothesis}
        if not role_only:
            result["severity"] = severity
        return json.dumps(result)
    if role == "planner":
        plan = {
            "normal": "monitor",
            "warning": "inspect",
            "critical": "human_review",
        }[cast("str", severity)]
        result = {"plan": plan}
        if not role_only:
            result["severity"] = severity
        return json.dumps(result)
    if role == "critic":
        result = {"verdict": "consistent"}
        if not role_only:
            result["severity"] = severity
        return json.dumps(result)
    raise ValueError("unknown reference role")
