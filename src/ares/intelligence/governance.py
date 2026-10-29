"""Govern proposals: severity determines the action; model contributes rationale only."""

from ares.intelligence.decisions import Decision, DecisionKind
from ares.supervisor import Assessment, Severity


def governed_decision(assessment: Assessment, proposal: Decision) -> Decision:
    """Normalize model over-escalation without ever downgrading observed severity."""
    if proposal.assessment_severity is not assessment.severity:
        raise ValueError("Mismatched assessment severity")
    required = {
        Severity.NORMAL: DecisionKind.OBSERVE,
        Severity.WARNING: DecisionKind.INVESTIGATE,
        Severity.CRITICAL: DecisionKind.REQUEST_REVIEW,
    }[assessment.severity]
    return Decision(
        kind=required,
        rationale=proposal.rationale,
        assessment_severity=assessment.severity,
    )
