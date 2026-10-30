"""Supervisor can still recommend an action category if model is unavailable."""

from ares.intelligence.decisions import Decision, DecisionKind
from ares.intelligence.degraded import govern_outcome
from ares.intelligence.resilience import OutcomeStatus, ProposalOutcome
from ares.simulation import DeviceSnapshot
from ares.supervisor import Assessment, Severity


def assessment(severity: Severity) -> Assessment:
    return Assessment(
        DeviceSnapshot("simulated", 1, 85.0, True),
        severity,
        "Simulated diagnostic",
        "Follow the supervisor guidance",
    )


def test_model_error_uses_deterministic_degraded_mode() -> None:
    for severity, expected in (
        (Severity.NORMAL, DecisionKind.OBSERVE),
        (Severity.WARNING, DecisionKind.INVESTIGATE),
        (Severity.CRITICAL, DecisionKind.REQUEST_REVIEW),
    ):
        result = govern_outcome(
            assessment(severity),
            ProposalOutcome(OutcomeStatus.MODEL_ERROR, None, "model_exception", 5.0),
        )
        assert result.kind is expected
        assert result.mode == "deterministic_degraded"
        assert result.model_accepted is False


def test_accepted_over_escalation_cannot_change_supervisor_category() -> None:
    raw = Decision(DecisionKind.REQUEST_REVIEW, "Escalate", Severity.NORMAL)
    result = govern_outcome(
        assessment(Severity.NORMAL),
        ProposalOutcome(OutcomeStatus.ACCEPTED, raw, None, 3.0),
    )
    assert result.kind is DecisionKind.OBSERVE
    assert result.mode == "model_advisory"
    assert result.explanation == "Follow the supervisor guidance"


def test_rejected_response_is_degraded() -> None:
    result = govern_outcome(
        assessment(Severity.CRITICAL),
        ProposalOutcome(OutcomeStatus.REJECTED, None, "invalid_decision", 2.0),
    )
    assert result.kind is DecisionKind.REQUEST_REVIEW
    assert result.mode == "deterministic_degraded"
