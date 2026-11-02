"""Third LLM role remains advisory; safety decision stays deterministic."""

import json

from pytest import CaptureFixture, MonkeyPatch

from ares.evaluation import bounded_team
from ares.evaluation.independent_review import independent_mean_review


def test_independent_mean_review_accepts_equivalent_numeric_answer() -> None:
    answer, passed = independent_mean_review(("55 C", "60 C", "65 C"), "60", lambda _: "60.0")
    assert answer == "60.0"
    assert passed


def test_independent_mean_review_rejects_wrong_result() -> None:
    answer, passed = independent_mean_review(("55 C", "60 C", "65 C"), "60", lambda _: "61")
    assert answer == "61"
    assert not passed


def test_independent_mean_review_fails_closed_when_model_fails() -> None:
    def failed(_prompt: str) -> str:
        raise RuntimeError("offline")

    assert independent_mean_review(("55 C", "60 C", "65 C"), "60", failed) == ("", False)


def test_cli_third_role_succeeds_without_model_risk_classification(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    def generator(_model: str) -> bounded_team.Generate:
        def generate(question: str) -> str:
            if question.startswith("Extract"):
                return question.split("sensor: ")[1].split(" C")[0]
            return "60"

        return generate

    monkeypatch.setattr(bounded_team, "ollama_generator", generator)
    assert bounded_team.run(["55", "60", "65", "--independent-review"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["severity"] == "warning"
    assert result["statistics"]["model_calls"] == 5
    assert result["statistics"]["model_steps_correct"] == 5
    assert result["statistics"]["independent_review_correct"] == 1


def test_cli_third_role_rejects_disagreement(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    def generator(_model: str) -> bounded_team.Generate:
        def generate(question: str) -> str:
            if question.startswith("Extract"):
                return question.split("sensor: ")[1].split(" C")[0]
            if question.startswith("Compute"):
                return "60"
            return "70"

        return generate

    monkeypatch.setattr(bounded_team, "ollama_generator", generator)
    assert bounded_team.run(["55", "60", "65", "--independent-review"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "rejected"
    assert result["severity"] is None
    assert result["errors"] == ["independent_review_mismatch"]
    assert result["statistics"]["model_steps_correct"] == 4
    assert result["statistics"]["model_steps_total"] == 5
    assert result["statistics"]["independent_review_total"] == 1
