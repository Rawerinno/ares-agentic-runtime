"""Non-causal hypotheses and checks for simulated temperature assessments."""

from dataclasses import dataclass
from enum import StrEnum

from ares.supervisor import Assessment, Severity


class HypothesisStatus(StrEnum):
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class InvestigationHypothesis:
    title: str
    verification: str
    status: HypothesisStatus = HypothesisStatus.UNVERIFIED


def suggested_checks(assessment: Assessment) -> tuple[InvestigationHypothesis, ...]:
    """Provide read-only checks, never claim a fault has been established."""
    if not assessment.snapshot.healthy:
        return (
            InvestigationHypothesis(
                "Sensor validity uncertain",
                "Compare with an independent calibrated measurement by a qualified operator.",
            ),
        )
    if assessment.severity is Severity.NORMAL:
        return ()
    return (
        InvestigationHypothesis(
            "Thermal load may have increased",
            "Review historical temperature trends and operating load.",
        ),
        InvestigationHypothesis(
            "Cooling performance may be reduced",
            "Ask a qualified operator to inspect cooling maintenance records.",
        ),
        InvestigationHypothesis(
            "Measurement or calibration may be inaccurate",
            "Compare against a calibrated independent instrument.",
        ),
    )
