"""Conservative consistency checks for rule-based simulated diagnostics."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from ares.intelligence.decisions import DecisionKind
from ares.intelligence.diagnostics import DiagnosticReport
from ares.intelligence.hypotheses import InvestigationHypothesis, HypothesisStatus
from ares.supervisor import Assessment, Severity


class FindingCode(StrEnum):
    RECOMMENDATION_MISMATCH = "recommendation_mismatch"
    SEVERITY_MISMATCH = "severity_mismatch"
    INVALID_SENSOR = "invalid_sensor"
    UNSUPPORTED_HYPOTHESIS = "unsupported_hypothesis"
    MODEL_DISAGREEMENT = "model_disagreement"


@dataclass(frozen=True, slots=True)
class ConsistencyResult:
    passed: bool
    findings: tuple[FindingCode, ...]


def check_consistency(
    assessment: Assessment,
    report: DiagnosticReport,
    hypotheses: tuple[InvestigationHypothesis, ...],
) -> ConsistencyResult:
    """Compare known structured fields; cannot fact-check natural-language claims."""
    issues: list[FindingCode] = []
    expected = {
        Severity.NORMAL: DecisionKind.OBSERVE,
        Severity.WARNING: DecisionKind.INVESTIGATE,
        Severity.CRITICAL: DecisionKind.REQUEST_REVIEW,
    }[assessment.severity]
    if report.severity is not assessment.severity:
        issues.append(FindingCode.SEVERITY_MISMATCH)
    if report.recommendation is not expected:
        issues.append(FindingCode.RECOMMENDATION_MISMATCH)
    if not assessment.snapshot.healthy or not isfinite(assessment.snapshot.temperature_c):
        issues.append(FindingCode.INVALID_SENSOR)
    if any(h.status is not HypothesisStatus.UNVERIFIED for h in hypotheses):
        issues.append(FindingCode.UNSUPPORTED_HYPOTHESIS)
    if assessment.severity is Severity.NORMAL and hypotheses:
        issues.append(FindingCode.UNSUPPORTED_HYPOTHESIS)
    if report.model_consistent is False:
        issues.append(FindingCode.MODEL_DISAGREEMENT)
    return ConsistencyResult(passed=not issues, findings=tuple(issues))
