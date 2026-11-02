"""Offline boundary tests: model arithmetic must never control risk decisions."""

import json

import pytest
from pytest import CaptureFixture, MonkeyPatch

from ares.evaluation import bounded_observation
from ares.evaluation.bounded_observation import observe


def extract_or_wrong_mean(prompt: str) -> str:
    if prompt.startswith("Extract"):
        return prompt.split("sensor: ", 1)[1].split(" C", 1)[0]
    return "999"


@pytest.mark.parametrize(
    ("readings", "expected_mean", "severity"),
    [
        (("55 C", "60 C", "65 C"), "60", "warning"),
        (("79 C", "80 C", "81 C"), "80", "critical"),
        (("-8 C", "-4 C", "0 C"), "-4", "normal"),
        (("61.5 C", "62.5 C", "63.5 C"), "62.5", "warning"),
    ],
)
def test_model_arithmetic_can_fail_without_corrupting_verified_result(
    readings: tuple[str, ...], expected_mean: str, severity: str
) -> None:
    report = observe(readings, extract_or_wrong_mean, evaluate_arithmetic=True)
    assert report.status == "verified"
    assert report.verified_mean == expected_mean
    assert report.severity == severity
    assert report.advisory_mean == "999"
    assert report.advisory_correct is False
    assert report.error_codes == ("advisory_arithmetic_mismatch",)


def test_default_does_not_invoke_model_for_arithmetic() -> None:
    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return extract_or_wrong_mean(prompt)

    result = observe(("55 C", "60 C", "65 C"), generate)
    assert result.status == "verified"
    assert result.advisory_mean is None
    assert len(prompts) == 3


def test_extract_mismatch_fail_closed_without_arithmetic_call() -> None:
    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return "0"

    result = observe(("55 C", "60 C", "65 C"), generate, evaluate_arithmetic=True)
    assert result.status == "rejected"
    assert result.verified_mean is None
    assert result.severity is None
    assert result.error_codes == ("extractor_mismatch",)
    assert len(prompts) == 3


def test_arithmetic_transport_exception_is_diagnostic_only() -> None:
    def generate(prompt: str) -> str:
        if prompt.startswith("Compute"):
            raise RuntimeError("offline")
        return extract_or_wrong_mean(prompt)

    result = observe(("55 C", "60 C", "65 C"), generate, evaluate_arithmetic=True)
    assert result.status == "verified"
    assert result.advisory_correct is False
    assert result.severity == "warning"


@pytest.mark.parametrize(
    "readings",
    [
        ("1e9999999 C", "60 C", "65 C"),
        ("NaN C", "60 C", "65 C"),
        ("59 C", "60 K", "65 C"),
    ],
)
def test_malformed_input_never_calls_model(readings: tuple[str, ...]) -> None:
    def forbidden(_prompt: str) -> str:
        raise AssertionError("unexpected model call")

    with pytest.raises(ValueError):
        observe(readings, forbidden)


def test_cli_reports_advisory_failure_and_correct_authority(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    def generator(_model: str) -> bounded_observation.Generate:
        return extract_or_wrong_mean

    monkeypatch.setattr(bounded_observation, "ollama_generator", generator)
    assert (
        bounded_observation.run(
            ["61.5", "62.5", "63.5", "--input-mode", "llm", "--evaluate-arithmetic"]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "verified"
    assert payload["severity"] == "warning"
    assert payload["advisory_correct"] is False
    assert payload["metrics"]["model_calls"] == 4
    assert payload["authority"] == "deterministic_python"
