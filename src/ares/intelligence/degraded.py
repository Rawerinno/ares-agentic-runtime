"""Deterministic read-only fallback when the untrusted model is unavailable."""

from dataclasses import dataclass

from ares.intelligence.decisions import DecisionKind
from ares.intelligence.resilience import OutcomeStatus, ProposalOutcome
from ares.supervisor import Assessment, Severity


@dataclass(frozen=True, slots=True)
class GovernedOutcome:
    kind: DecisionKind
    mode: str
    model_accepted: bool
    explanation: str


def govern_outcome(assessment: Assessment, outcome: ProposalOutcome) -> GovernedOutcome:
    """Select diagnostic category from supervisor, never model text."""
    required = {
        Severity.NORMAL: DecisionKind.OBSERVE,
        Severity.WARNING: DecisionKind.INVESTIGATE,
        Severity.CRITICAL: DecisionKind.REQUEST_REVIEW,
    }[assessment.severity]
    accepted = outcome.status is OutcomeStatus.ACCEPTED and outcome.decision is not None
    return GovernedOutcome(
        kind=required,
        mode="model_advisory" if accepted else "deterministic_degraded",
        model_accepted=accepted,
        explanation=assessment.recommendation,
    )
