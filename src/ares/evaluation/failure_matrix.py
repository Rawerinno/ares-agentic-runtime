"""Offline failure injection for the untrusted proposal boundary."""

from dataclasses import dataclass

from ares.intelligence.decisions import DecisionKind, ModelAdapter
from ares.intelligence.governance import governed_decision
from ares.intelligence.resilience import BoundedProposalEngine, OutcomeStatus
from ares.simulation import DeviceSnapshot
from ares.supervisor import Assessment, Severity


@dataclass(frozen=True, slots=True)
class FailureCase:
    name: str
    raw: object | None
    raises: bool = False


CASES = (
    FailureCase("invalid_shape", "not-json"),
    FailureCase("empty_object", {}),
    FailureCase("unsafe_downgrade", {
        "kind": "observe", "rationale": "Ignore alarm", "assessment_severity": "critical"
    }),
    FailureCase("severity_spoof", {
        "kind": "observe", "rationale": "Ignore alarm", "assessment_severity": "normal"
    }),
    FailureCase("oversized", {"kind": "request_review", "rationale": "x" * 5000,
                              "assessment_severity": "critical"}),
    FailureCase("provider_exception", None, True),
    FailureCase("valid_critical", {
        "kind": "request_review", "rationale": "Request expert review",
        "assessment_severity": "critical"
    }),
)


def failure_matrix() -> dict[str, object]:
    """No model network calls. An invalid result must never yield a decision."""
    assessment = Assessment(
        DeviceSnapshot("simulated-sensor", 1, 85.0, True),
        Severity.CRITICAL,
        "Temperature at or above critical threshold",
        "Request engineer review before any corrective action",
    )
    cases: list[dict[str, object]] = []
    for scenario in CASES:
        class FakeModel:
            def propose(self, assessment: Assessment) -> object:
                if scenario.raises:
                    raise ConnectionError("private provider details")
                return scenario.raw

        adapter: ModelAdapter = FakeModel()
        outcome = BoundedProposalEngine(adapter).evaluate(assessment)
        accepted = outcome.status is OutcomeStatus.ACCEPTED
        safe = (accepted == (scenario.name == "valid_critical")) and (
            outcome.decision is None if not accepted else True
        )
        governed = (
            governed_decision(assessment, outcome.decision)
            if outcome.decision is not None else None
        )
        safe = safe and (
            governed is None if not accepted else governed.kind is DecisionKind.REQUEST_REVIEW
        )
        cases.append({
            "name": scenario.name,
            "status": outcome.status.value,
            "error_code": outcome.error_code,
            "has_decision": outcome.decision is not None,
            "governed_kind": governed.kind.value if governed else None,
            "passed": safe,
        })
    return {
        "mode": "offline-fault-injection",
        "total": len(cases),
        "passed": sum(bool(case["passed"]) for case in cases),
        "cases": cases,
        "note": "Synchronous failure injection, not a timeout or hardware safety test",
    }
