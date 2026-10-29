"""Diagnostic quality distinguishes structural checks and textual validation."""

from ares.evaluation.diagnostic_quality import assess_quality
from ares.intelligence.consistency import check_consistency
from ares.intelligence.decisions import Decision, DecisionKind
from ares.intelligence.diagnostics import build_diagnostic_report
from ares.intelligence.hypotheses import suggested_checks
from ares.simulation import DeviceSnapshot
from ares.supervisor import Assessment, Severity


def test_disagreement_is_visible_without_claiming_text_validation() -> None:
    observation = Assessment(
        DeviceSnapshot("sensor", 1, 20.0, True),
        Severity.NORMAL,
        "Within threshold",
        "Continue observation",
    )
    raw = Decision(DecisionKind.REQUEST_REVIEW, "Escalate", Severity.NORMAL)
    report = build_diagnostic_report(observation, raw)
    consistency = check_consistency(observation, report, suggested_checks(observation))
    quality = assess_quality(observation, report, consistency)
    assert quality.governed_category_valid
    assert quality.evidence_present
    assert quality.model_agreement is False
    assert quality.free_text_verified is False
    assert len(quality.structural_findings) == 1
