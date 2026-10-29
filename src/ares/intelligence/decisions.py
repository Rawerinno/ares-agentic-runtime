"""Strict proposal-only AI contracts; never a tool execution interface."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, cast

from ares.supervisor import Assessment, Severity


class DecisionError(ValueError):
    """Invalid or unsupported model output."""


class DecisionKind(StrEnum):
    OBSERVE = "observe"
    INVESTIGATE = "investigate"
    REQUEST_REVIEW = "request_review"


@dataclass(frozen=True, slots=True)
class Decision:
    """Auditable text recommendation without operational authority."""

    kind: DecisionKind
    rationale: str
    assessment_severity: Severity

    def __post_init__(self) -> None:
        if type(self.kind) is not DecisionKind:
            raise DecisionError("Unknown decision kind")
        if type(self.assessment_severity) is not Severity:
            raise DecisionError("Unknown severity")
        if not self.rationale.strip() or len(self.rationale) > 1000:
            raise DecisionError("Rationale must be 1..1000 nonblank characters")


class ModelAdapter(Protocol):
    """Untrusted model output interface; implementations cannot invoke tools."""

    def propose(self, assessment: Assessment) -> object:
        """Return untrusted structured data."""


class ProposalEngine:
    """Validate untrusted proposals and forbid unsafe severity downgrades."""

    def __init__(self, model: ModelAdapter) -> None:
        self._model = model

    def propose(self, assessment: Assessment) -> Decision:
        raw = self._model.propose(assessment)
        if not isinstance(raw, dict) or set(cast("dict[str, object]", raw)) != {
            "kind",
            "rationale",
            "assessment_severity",
        }:
            raise DecisionError("Model output must have exactly three fields")
        fields = cast("dict[str, object]", raw)
        kind = fields["kind"]
        reason = fields["rationale"]
        severity = fields["assessment_severity"]
        if type(kind) is not str or type(reason) is not str or type(severity) is not str:
            raise DecisionError("Model fields must be strings")
        try:
            decision = Decision(DecisionKind(kind), reason, Severity(severity))
        except ValueError as exc:
            raise DecisionError("Invalid model decision") from exc
        if decision.assessment_severity is not assessment.severity:
            raise DecisionError("Model may not alter observed severity")
        if (
            assessment.severity is Severity.CRITICAL
            and decision.kind is not DecisionKind.REQUEST_REVIEW
        ):
            raise DecisionError("Critical telemetry requires human review")
        if assessment.severity is Severity.WARNING and decision.kind is DecisionKind.OBSERVE:
            raise DecisionError("Warning telemetry cannot be dismissed")
        return decision
