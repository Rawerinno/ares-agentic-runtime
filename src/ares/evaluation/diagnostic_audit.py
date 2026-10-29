"""Privacy-minimized audit projection for simulated diagnostic decisions."""

from ares.evaluation.audit import AuditEntry, append_entry
from ares.intelligence.consistency import ConsistencyResult
from ares.intelligence.diagnostics import DiagnosticReport
from ares.intelligence.resilience import ProposalOutcome
from ares.supervisor import Assessment


def record_diagnostic(
    entries: tuple[AuditEntry, ...],
    assessment: Assessment,
    report: DiagnosticReport,
    outcome: ProposalOutcome,
    consistency: ConsistencyResult,
) -> tuple[AuditEntry, ...]:
    """Record codes and numeric reading, not prompts or model rationale."""
    if report.severity is not assessment.severity:
        raise ValueError("Inconsistent diagnostic severity")
    payload: dict[str, object] = {
        "temperature_c": assessment.snapshot.temperature_c,
        "sensor_healthy": assessment.snapshot.healthy,
        "severity": assessment.severity.value,
        "governed_recommendation": report.recommendation.value,
        "model_status": outcome.status.value,
        "model_recommendation": (
            outcome.decision.kind.value if outcome.decision is not None else None
        ),
        "model_consistent": report.model_consistent,
        "consistency_findings": [finding.value for finding in consistency.findings],
    }
    return append_entry(entries, "diagnostic_assessed", payload)
