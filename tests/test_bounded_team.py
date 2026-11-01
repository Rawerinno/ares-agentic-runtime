"""Test the bounded three-role ARES pipeline without Ollama or hardware."""

import pytest

from ares.evaluation.bounded_team import evaluate_team


def fake_model(question: str) -> str:
    if "Extract" in question:
        return question.split("sensor: ")[1].split(" C")[0]
    if "arithmetic mean" in question:
        return "60.0"
    raise ValueError("unexpected question")


def test_verified_warning_decided_deterministically() -> None:
    report = evaluate_team(("55 C", "60 C", "65 C"), fake_model)
    assert report.status == "verified"
    assert report.severity == "warning"
    assert report.verified_mean == "60"


def test_incorrect_model_arithmetic_rejected() -> None:
    def wrong(question: str) -> str:
        return "normal" if "mean" in question else fake_model(question)

    report = evaluate_team(("55 C", "60 C", "65 C"), wrong)
    assert report.status == "rejected"
    assert report.severity is None
    assert report.errors == ("arithmetic_mismatch",)


def test_incorrect_model_extraction_rejected() -> None:
    def wrong(question: str) -> str:
        if "Extract" in question:
            return "999"
        return "60"

    report = evaluate_team(("55 C", "60 C", "65 C"), wrong)
    assert report.status == "rejected"
    assert report.errors == ("extractor_mismatch",)


def test_model_failure_rejected_without_fallback_authority() -> None:
    def failed(_question: str) -> str:
        raise RuntimeError("ollama offline")

    report = evaluate_team(("55 C", "60 C", "65 C"), failed)
    assert report.status == "rejected"
    assert report.severity is None


@pytest.mark.parametrize(
    "bad",
    [
        ("20 C", "30 C"),
        ("NaN C", "20 C", "30 C"),
        ("20 C", "30 K", "40 C"),
        ("20 C", "unexpected 30 C", "40 C"),
    ],
)
def test_invalid_measurements_rejected_before_model(bad: tuple[str, ...]) -> None:
    def must_not_run(_question: str) -> str:
        raise AssertionError("model must not be used for invalid input")

    with pytest.raises(ValueError):
        evaluate_team(bad, must_not_run)


def test_critical_classification_not_model_decision() -> None:
    def model(question: str) -> str:
        if "Extract" in question:
            return question.split("sensor: ")[1].split(" C")[0]
        return "85.0"

    report = evaluate_team(("80 C", "85 C", "90 C"), model)
    assert report.status == "verified"
    assert report.severity == "critical"
