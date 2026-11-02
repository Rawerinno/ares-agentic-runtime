"""CLI metrics accurately count multiple model errors; no local Ollama needed."""

import json

from pytest import CaptureFixture, MonkeyPatch

from ares.evaluation import bounded_team


def test_cli_counts_each_incorrect_extraction(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    def fake_model(_model: str) -> bounded_team.Generate:
        def generate(question: str) -> str:
            if "sensor: 55 C" in question:
                return "55"
            return "999"

        return generate

    monkeypatch.setattr(bounded_team, "ollama_generator", fake_model)
    exit_code = bounded_team.run(["55", "60", "65"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["status"] == "rejected"
    assert payload["severity"] is None
    assert payload["statistics"]["model_calls"] == 3
    assert payload["statistics"]["extraction_correct"] == 1
    assert payload["statistics"]["extraction_total"] == 3
    assert payload["statistics"]["model_steps_accuracy"] == 0.3333


def test_cli_reports_success_when_each_step_is_correct(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    def fake_model(_model: str) -> bounded_team.Generate:
        def generate(question: str) -> str:
            if "Extract" in question:
                return question.split("sensor: ")[1].split(" C")[0]
            return "60.0"

        return generate

    monkeypatch.setattr(bounded_team, "ollama_generator", fake_model)
    exit_code = bounded_team.run(["55", "60", "65"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["statistics"]["model_steps_correct"] == 4
    assert payload["statistics"]["model_steps_total"] == 4
    assert payload["statistics"]["model_steps_accuracy"] == 1.0
    assert payload["scheduling_decision"]["parallelism"] == 1
