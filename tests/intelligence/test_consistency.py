"""Structured checks identify policy and evidence inconsistencies."""

from dataclasses import replace

from ares.intelligence.consistency import FindingCode, check_consistency
from ares.intelligence.decisions import Decision, DecisionKind
from ares.intelligence.diagnostics import build_diagnostic_report
from ares.intelligence.hypotheses import HypothesisStatus, suggested_checks
from ares.simulation import DeviceSnapshot
from ares.supervisor import Assessment, Severity


def assessment(severity: Severity, healthy: bool = True) -> Assessment:
    return Assessment(DeviceSnapshot("sensor", 1, 85.0, healthy), severity, "Rule", "Review")


def test_consistent_critical_assessment() -> None:
    item = assessment(Severity.CRITICAL)
    report = build_diagnostic_report(item)
    result = check_consistency(item, report, suggested_checks(item))
    assert result.passed
    assert result.findings == ()


def test_over_escalation_detected_but_governed_category_preserved() -> None:
    item = assessment(Severity.NORMAL)
    proposal = Decision(DecisionKind.REQUEST_REVIEW, "Escalate", Severity.NORMAL)
    report = build_diagnostic_report(item, proposal)
    result = check_consistency(item, report, suggested_checks(item))
    assert result.findings == (FindingCode.MODEL_DISAGREEMENT,)


def test_mismatched_report_and_unsupported_hypotheses() -> None:
    item = assessment(Severity.NORMAL)
    report = replace(
        build_diagnostic_report(item),
        severity=Severity.WARNING,
        recommendation=DecisionKind.INVESTIGATE,
    )
    hypotheses = suggested_checks(assessment(Severity.WARNING))
    result = check_consistency(item, report, hypotheses)
    assert FindingCode.SEVERITY_MISMATCH in result.findings
    assert FindingCode.RECOMMENDATION_MISMATCH in result.findings
    assert FindingCode.UNSUPPORTED_HYPOTHESIS in result.findings


def test_invalid_sensor_is_flagged() -> None:
    item = assessment(Severity.CRITICAL, healthy=False)
    result = check_consistency(item, build_diagnostic_report(item), suggested_checks(item))
    assert FindingCode.INVALID_SENSOR in result.findings


def test_status_enum_is_unverified() -> None:
    assert HypothesisStatus.UNVERIFIED.value == "unverified"
