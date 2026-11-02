"""Structured temperature inputs bypass the model completely."""

import json

import pytest
from pytest import CaptureFixture, MonkeyPatch

from ares.evaluation import bounded_observation
from ares.evaluation.bounded_observation import observe_structured


@pytest.mark.parametrize(
    ("readings", "mean", "severity"),
    [
        (("55 C", "60 C", "65 C"), "60", "warning"),
        (("-8 C", "-4 C", "0 C"), "-4", "normal"),
        (("61.5 C", "62.5 C", "63.5 C"), "62.5", "warning"),
        (("79 C", "80 C", "81 C"), "80", "critical"),
    ],
)
def test_structured_math_is_exact_and_model_free(
    readings: tuple[str, ...], mean: str, severity: str
) -> None:
    result = observe_structured(readings)
    assert result.status == "verified"
    assert result.verified_mean == mean
    assert result.severity == severity
    assert result.advisory_mean is None


@pytest.mark.parametrize(
    "readings",
    [
        ("NaN C", "60 C", "65 C"),
        ("1e99999 C", "60 C", "65 C"),
        ("55 C", "60 F", "65 C"),
        ("55 C", "invalid 60 C", "65 C"),
    ],
)
def test_structured_rejects_malformed_inputs(readings: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        observe_structured(readings)


def test_cli_default_never_connects_to_ollama(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    def model_must_not_load(_model: str) -> bounded_observation.Generate:
        raise AssertionError("Ollama should not be called for structured values")

    monkeypatch.setattr(bounded_observation, "ollama_generator", model_must_not_load)
    assert bounded_observation.run(["-8", "-4", "0"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["verified_mean"] == "-4"
    assert payload["severity"] == "normal"
    assert payload["input_mode"] == "structured"
    assert payload["model_authority"] == "none"
    assert payload["metrics"]["model_calls"] == 0
    assert payload["metrics"]["mean_latency_ms"] is None


def test_llm_path_remains_opt_in(monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]) -> None:
    prompts: list[str] = []

    def loader(_model: str) -> bounded_observation.Generate:
        def model(prompt: str) -> str:
            prompts.append(prompt)
            return prompt.split("sensor: ", 1)[1].split(" C", 1)[0]

        return model

    monkeypatch.setattr(bounded_observation, "ollama_generator", loader)
    assert bounded_observation.run(["55", "60", "65", "--input-mode", "llm"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["metrics"]["model_calls"] == 3
    assert len(prompts) == 3
    assert result["input_mode"] == "llm"
