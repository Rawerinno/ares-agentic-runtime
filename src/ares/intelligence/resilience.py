"""Bounded validation and auditable outcomes for untrusted model proposals.

No network operations, tool execution or implicit retries are performed.
"""
from dataclasses import dataclass
from enum import StrEnum
from time import monotonic

from ares.intelligence.decisions import Decision, DecisionError, ModelAdapter, ProposalEngine
from ares.supervisor import Assessment


class OutcomeStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MODEL_ERROR = "model_error"


@dataclass(frozen=True, slots=True)
class ProposalOutcome:
    status: OutcomeStatus
    decision: Decision | None
    error_code: str | None
    elapsed_ms: float


class BoundedProposalEngine:
    """Record proposal outcomes; reject oversized JSON-like model data.

    This is a synchronous boundary. It measures elapsed time but does NOT
    interrupt hanging model calls. Real timeout enforcement belongs in the
    provider/transport adapter and is required before enabling remote models.
    """

    def __init__(self, model: ModelAdapter, *, max_response_chars: int = 4096) -> None:
        if max_response_chars < 1:
            raise ValueError("max_response_chars must be positive")
        self._model = model
        self._limit = max_response_chars

    def evaluate(self, assessment: Assessment) -> ProposalOutcome:
        started = monotonic()
        try:
            raw = self._model.propose(assessment)
        except Exception:
            return self._outcome(OutcomeStatus.MODEL_ERROR, None, "model_exception", started)
        if not isinstance(raw, dict):
            return self._outcome(OutcomeStatus.REJECTED, None, "invalid_shape", started)
        if len(str(raw)) > self._limit:
            return self._outcome(OutcomeStatus.REJECTED, None, "response_too_large", started)
        try:
            class ReturnedModel:
                def propose(self, observation: Assessment) -> object:
                    return raw

            decision = ProposalEngine(ReturnedModel()).propose(assessment)
        except DecisionError:
            return self._outcome(OutcomeStatus.REJECTED, None, "invalid_decision", started)
        return self._outcome(OutcomeStatus.ACCEPTED, decision, None, started)

    @staticmethod
    def _outcome(
        status: OutcomeStatus,
        decision: Decision | None,
        error_code: str | None,
        started: float,
    ) -> ProposalOutcome:
        return ProposalOutcome(status, decision, error_code, (monotonic() - started) * 1000)
