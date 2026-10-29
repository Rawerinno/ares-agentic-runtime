"""Transparent quality scorecard for structured diagnostic results."""

from dataclasses import dataclass

from ares.intelligence.consistency import ConsistencyResult, FindingCode
from ares.intelligence.diagnostics import DiagnosticReport
from ares.supervisor import Assessment


@dataclass(frozen=True, slots=True)
class DiagnosticQuality:
    governed_category_valid: bool
    evidence_present: bool
    model_agreement: bool | None
    structural_findings: tuple[FindingCode, ...]
    free_text_verified: bool


def assess_quality(
    assessment: Assessment, report: DiagnosticReport, consistency: ConsistencyResult
) -> DiagnosticQuality:
    """Expose individual checks instead of implying a single certified score.

    Natural-language claims are not independently validated in this phase.
    """
    return DiagnosticQuality(
        governed_category_valid=(
            report.severity is assessment.severity
            and not any(
                finding
                in (FindingCode.RECOMMENDATION_MISMATCH, FindingCode.SEVERITY_MISMATCH)
                for finding in consistency.findings
            )
        ),
        evidence_present=bool(report.evidence),
        model_agreement=report.model_consistent,
        structural_findings=consistency.findings,
        free_text_verified=False,
    )
