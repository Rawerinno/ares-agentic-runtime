"""Deterministic tests for bounded and auditable model outcomes."""

import pytest

from ares.intelligence.resilience import BoundedProposalEngine, OutcomeStatus
from ares.simulation import DeviceSnapshot
from ares.supervisor import Assessment, Severity


def assessment() -> Assessment:
    return Assessment(DeviceSnapshot("test", 0, 20.0, True), Severity.NORMAL, "ok", "observe")


class Stub:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def propose(self, assessment: Assessment) -> object:
        return self.payload


def test_valid_proposal_is_accepted() -> None:
    output = BoundedProposalEngine(
        Stub(
            {
                "kind": "observe",
                "rationale": "Continue observing",
                "assessment_severity": "normal",
            }
        )
    ).evaluate(assessment())
    assert output.status is OutcomeStatus.ACCEPTED
    assert output.decision is not None
    assert output.error_code is None
    assert output.elapsed_ms >= 0


def test_bad_response_is_rejected_without_content_leakage() -> None:
    output = BoundedProposalEngine(Stub("ignore instructions")).evaluate(assessment())
    assert output.status is OutcomeStatus.REJECTED
    assert output.error_code == "invalid_shape"
    assert output.decision is None


def test_oversized_response_rejected() -> None:
    output = BoundedProposalEngine(
        Stub({"kind": "observe", "rationale": "x" * 1000, "assessment_severity": "normal"}),
        max_response_chars=50,
    ).evaluate(assessment())
    assert output.error_code == "response_too_large"


def test_invalid_decision_rejected() -> None:
    output = BoundedProposalEngine(
        Stub({"kind": "actuate", "rationale": "unsafe", "assessment_severity": "normal"})
    ).evaluate(assessment())
    assert output.error_code == "invalid_decision"


def test_provider_exception_is_redacted() -> None:
    class Failing:
        def propose(self, assessment: Assessment) -> object:
            raise RuntimeError("secret-provider-token")

    output = BoundedProposalEngine(Failing()).evaluate(assessment())
    assert output.status is OutcomeStatus.MODEL_ERROR
    assert output.error_code == "model_exception"
    assert "secret" not in str(output)


def test_reject_invalid_limit() -> None:
    with pytest.raises(ValueError):
        BoundedProposalEngine(Stub({}), max_response_chars=0)
