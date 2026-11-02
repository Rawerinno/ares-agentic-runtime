"""No-model-cost tests for untrusted structured proposal validation."""

import pytest

from ares.intelligence import DecisionError, ProposalEngine
from ares.simulation import DeviceSnapshot
from ares.supervisor import Assessment, Severity


class FakeModel:
    def __init__(self, output: object) -> None:
        self.output = output

    def propose(self, assessment: Assessment) -> object:
        return self.output


def observation(severity: Severity) -> Assessment:
    return Assessment(
        DeviceSnapshot("sim", 0, 80.0, True),
        severity,
        "Measured temperature",
        "Inspect",
    )


def payload(
    kind: str = "request_review",
    severity: str = "critical",
    rationale: str = "Escalate to an engineer",
) -> dict[str, str]:
    return {"kind": kind, "assessment_severity": severity, "rationale": rationale}


def test_critical_requires_review() -> None:
    result = ProposalEngine(FakeModel(payload())).propose(observation(Severity.CRITICAL))
    assert result.kind == "request_review"


def test_normal_observation_allowed() -> None:
    result = ProposalEngine(FakeModel(payload("observe", "normal"))).propose(
        observation(Severity.NORMAL)
    )
    assert result.kind == "observe"


def test_warning_investigation_allowed() -> None:
    result = ProposalEngine(FakeModel(payload("investigate", "warning"))).propose(
        observation(Severity.WARNING)
    )
    assert result.kind == "investigate"


@pytest.mark.parametrize(
    "output",
    [
        None,
        [],
        {},
        payload("activate_device"),
        payload("observe"),
        payload("investigate"),
        payload("request_review", "normal"),
        payload("request_review", "critical", ""),
        payload("request_review", "critical", "x" * 1001),
        {
            "kind": "request_review",
            "rationale": "ok",
            "assessment_severity": "critical",
            "extra": 1,
        },
        {"kind": 1, "rationale": "ok", "assessment_severity": "critical"},
        {"kind": "request_review", "rationale": 1, "assessment_severity": "critical"},
        {"kind": "request_review", "rationale": "ok", "assessment_severity": 1},
    ],
)
def test_bad_or_unsafe_model_outputs_rejected(output: object) -> None:
    with pytest.raises(DecisionError):
        ProposalEngine(FakeModel(output)).propose(observation(Severity.CRITICAL))


def test_warning_cannot_be_dismissed() -> None:
    with pytest.raises(DecisionError):
        ProposalEngine(FakeModel(payload("observe", "warning"))).propose(
            observation(Severity.WARNING)
        )


def test_model_failure_is_not_silently_accepted() -> None:
    class BrokenModel:
        def propose(self, assessment: Assessment) -> object:
            raise RuntimeError("Offline")

    with pytest.raises(RuntimeError, match="Offline"):
        ProposalEngine(BrokenModel()).propose(observation(Severity.NORMAL))


@pytest.mark.parametrize(
    ("severity", "kind"),
    [
        (Severity.NORMAL, "investigate"),
        (Severity.NORMAL, "request_review"),
        (Severity.WARNING, "observe"),
        (Severity.WARNING, "request_review"),
        (Severity.CRITICAL, "observe"),
        (Severity.CRITICAL, "investigate"),
    ],
)
def test_severity_specific_policy_rejects_extra_or_missing_escalation(
    severity: Severity, kind: str
) -> None:
    with pytest.raises(DecisionError, match="deterministic policy"):
        ProposalEngine(FakeModel(payload(kind, severity.value))).propose(observation(severity))
