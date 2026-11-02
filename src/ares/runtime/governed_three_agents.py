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


class GovernedThreeAgentTeam:
    """Investigator, planner, critic; each provides bounded advisory enums."""

    def __init__(self, generate: Generate, *, identity: str = "three-role-v1") -> None:
        if not identity.strip() or len(identity) > 120:
            raise ValueError("team identity must be 1..120 nonblank characters")
        self._generate = generate
        self.identity = identity

    def evaluate(self, assessment: Assessment) -> TeamOutcome:
        from ares.runtime.multi_agent_mvp import RoleHandoff

        severity = assessment.severity.value
        healthy = assessment.snapshot.healthy
        hypothesis = (
            "sensor_fault"
            if not healthy
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
        handoffs: list[RoleHandoff] = []
        calls = 0
        for role, expected, instruction in descriptions:
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
                f"ROLE={role}. {instruction}. You have NO tool permissions. "
                "The severity is fixed by Python and must not change. "
                f"Trusted context: {json.dumps(trusted, allow_nan=False)}. "
                "Respond with ONLY a JSON object (as your answer string) "
                f"containing exactly these keys and values: {json.dumps(expected)}."
            )
            calls += 1
            try:
                answer = self._generate(question)
            except Exception:
                handoffs.append(
                    RoleHandoff(role, "Rejected: model_exception", "Deterministic fallback")
                )
                return TeamOutcome("rejected", tuple(handoffs), calls, "model_exception")
            try:
                if len(answer) > 256:
                    raise ValueError("oversized response")
                parsed: object = json.loads(answer)
                if not isinstance(parsed, dict):
                    raise ValueError("invalid response")
                actual = cast("dict[str, object]", parsed)
                if actual != expected or any(type(value) is not str for value in actual.values()):
                    raise ValueError("policy mismatch")
            except (ValueError, TypeError):
                handoffs.append(
                    RoleHandoff(role, "Rejected: policy_mismatch", "Deterministic fallback")
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
