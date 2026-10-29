"""Diagnostic reports preserve trust boundaries and evidence provenance."""

from ares.intelligence.decisions import Decision, DecisionKind
from ares.intelligence.diagnostics import EvidenceSource, build_diagnostic_report
from ares.simulation import DeviceSnapshot
from ares.supervisor import Assessment, Severity


def make_assessment(severity: Severity) -> Assessment:
    return Assessment(
        DeviceSnapshot("sensor", 1, 20.0, True),
        severity,
        "Rule-based temperature classification",
        "Continue observation",
    )


def test_normal_report_has_evidence_and_no_model_claim() -> None:
    report = build_diagnostic_report(make_assessment(Severity.NORMAL))
    assert report.recommendation is DecisionKind.OBSERVE
    assert report.model_suggestion is None
    assert report.model_consistent is None
    assert report.evidence[0].source is EvidenceSource.SENSOR
    assert "20.0 C" in report.evidence[0].fact
    assert "no root cause established" in report.limitation


def test_over_escalation_does_not_become_explanation() -> None:
    assessment = make_assessment(Severity.NORMAL)
    proposal = Decision(DecisionKind.REQUEST_REVIEW, "Shut down equipment", Severity.NORMAL)
    report = build_diagnostic_report(assessment, proposal)
    assert report.recommendation is DecisionKind.OBSERVE
    assert report.model_consistent is False
    assert report.model_suggestion is None
    assert report.explanation == "Continue observation"


def test_consistent_model_text_stays_separate() -> None:
    assessment = make_assessment(Severity.CRITICAL)
    proposal = Decision(DecisionKind.REQUEST_REVIEW, "Review reading", Severity.CRITICAL)
    report = build_diagnostic_report(assessment, proposal)
    assert report.recommendation is DecisionKind.REQUEST_REVIEW
    assert report.model_consistent is True
    assert report.model_suggestion == "Review reading"


def test_severity_mismatch_fails_closed() -> None:
    import pytest

    assessment = make_assessment(Severity.WARNING)
    proposal = Decision(DecisionKind.REQUEST_REVIEW, "Incorrect", Severity.CRITICAL)
    with pytest.raises(ValueError, match="severity"):
        build_diagnostic_report(assessment, proposal)
