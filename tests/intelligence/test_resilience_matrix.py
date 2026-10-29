"""Scenario matrix for bounded proposal validation."""

from ares.intelligence.resilience import BoundedProposalEngine, OutcomeStatus
from ares.simulation import DeviceSnapshot
from ares.supervisor import Assessment, Severity


class Stub:
    def __init__(self, output: object) -> None:
        self.output = output

    def propose(self, assessment: Assessment) -> object:
        return self.output


def evaluate(severity: Severity, output: object) -> OutcomeStatus:
    assessment = Assessment(
        DeviceSnapshot("sensor", 0, 85.0, True),
        severity,
        "test",
        "review",
    )
    return BoundedProposalEngine(Stub(output)).evaluate(assessment).status


def test_policy_matrix() -> None:
    cases: tuple[tuple[Severity, str, OutcomeStatus], ...] = (
        (Severity.NORMAL, "observe", OutcomeStatus.ACCEPTED),
        (Severity.WARNING, "observe", OutcomeStatus.REJECTED),
        (Severity.WARNING, "investigate", OutcomeStatus.ACCEPTED),
        (Severity.CRITICAL, "investigate", OutcomeStatus.REJECTED),
        (Severity.CRITICAL, "request_review", OutcomeStatus.ACCEPTED),
    )
    for severity, kind, expected in cases:
        output = {
            "kind": kind,
            "rationale": "Review the result",
            "assessment_severity": severity.value,
        }
        assert evaluate(severity, output) is expected
