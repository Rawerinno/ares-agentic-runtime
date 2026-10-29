"""Governance never grants the model authority over diagnostic action category."""

from ares.intelligence.decisions import Decision, DecisionKind
from ares.intelligence.governance import governed_decision
from ares.simulation import DeviceSnapshot
from ares.supervisor import Assessment, Severity


def test_over_escalation_is_corrected_without_reusing_rationale() -> None:
    assessment = Assessment(
        DeviceSnapshot("sensor", 1, 20.0, True),
        Severity.NORMAL,
        "Normal telemetry",
        "Continue observation",
    )
    raw = Decision(DecisionKind.REQUEST_REVIEW, "Call engineer immediately", Severity.NORMAL)
    result = governed_decision(assessment, raw)
    assert result.kind is DecisionKind.OBSERVE
    assert result.rationale == "Continue observation"


def test_critical_review_is_preserved() -> None:
    assessment = Assessment(
        DeviceSnapshot("sensor", 1, 85.0, True),
        Severity.CRITICAL,
        "High temperature",
        "Request engineer review",
    )
    raw = Decision(DecisionKind.REQUEST_REVIEW, "Escalate", Severity.CRITICAL)
    result = governed_decision(assessment, raw)
    assert result.kind is DecisionKind.REQUEST_REVIEW
    assert result.rationale == "Escalate"
