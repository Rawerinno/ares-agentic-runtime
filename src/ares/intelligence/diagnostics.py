"""Evidence-backed diagnostic reports; LLM text is never authoritative evidence."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from ares.intelligence.decisions import Decision, DecisionKind
from ares.supervisor import Assessment, Severity


class EvidenceSource(StrEnum):
    SENSOR = "sensor"
    SUPERVISOR = "supervisor"


@dataclass(frozen=True, slots=True)
class Evidence:
    source: EvidenceSource
    fact: str


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    severity: Severity
    recommendation: DecisionKind
    evidence: tuple[Evidence, ...]
    explanation: str
    model_suggestion: str | None
    model_consistent: bool | None
    limitation: str


def build_diagnostic_report(
    assessment: Assessment, proposal: Decision | None = None
) -> DiagnosticReport:
    """Keep operational classification deterministic and model text untrusted.

    Inconsistent, oversized or unrelated model rationales must not replace the
    trusted explanation; no causal claim can be established from one reading.
    """
    required = {
        Severity.NORMAL: DecisionKind.OBSERVE,
        Severity.WARNING: DecisionKind.INVESTIGATE,
        Severity.CRITICAL: DecisionKind.REQUEST_REVIEW,
    }[assessment.severity]
    if proposal is not None and proposal.assessment_severity is not assessment.severity:
        raise ValueError("Proposal severity does not match evidence")
    snapshot = assessment.snapshot
    temperature = (
        f"{snapshot.temperature_c:.1f} C" if isfinite(snapshot.temperature_c) else "non-finite"
    )
    evidence = (
        Evidence(EvidenceSource.SENSOR, f"Temperature reading: {temperature}"),
        Evidence(EvidenceSource.SENSOR, f"Sensor healthy: {snapshot.healthy}"),
        Evidence(EvidenceSource.SUPERVISOR, f"Rule-based severity: {assessment.severity.value}"),
        Evidence(EvidenceSource.SUPERVISOR, f"Rule-based reason: {assessment.reason}"),
    )
    consistent = proposal.kind is required if proposal is not None else None
    suggestion = proposal.rationale if proposal is not None and consistent else None
    return DiagnosticReport(
        severity=assessment.severity,
        recommendation=required,
        evidence=evidence,
        explanation=assessment.recommendation,
        model_suggestion=suggestion,
        model_consistent=consistent,
        limitation=(
            "Single simulated sensor observation; no root cause established. "
            "Model suggestions are unverified and cannot authorize device actions."
        ),
    )
