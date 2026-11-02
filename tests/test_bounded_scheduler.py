"""Bounded extraction scheduler tests (offline, no Ollama or network)."""

from threading import Lock

import pytest

from ares.evaluation.bounded_team import evaluate_team


def _stub(question: str) -> str:
    if "Extract" in question:
        return question.split("sensor: ")[1].split(" C")[0]
    if "arithmetic mean" in question:
        return "60"
    raise AssertionError("unexpected prompt")


@pytest.mark.parametrize("parallelism", [1, 2, 3])
def test_scheduler_preserves_verified_results(parallelism: int) -> None:
    result = evaluate_team(
        ("55 C", "60 C", "65 C"), _stub, parallelism=parallelism
    )
    assert result.status == "verified"
    assert result.severity == "warning"
    assert result.model_mean == "60"
    assert result.extracted == ("55", "60", "65")


@pytest.mark.parametrize("parallelism", [0, 4, -1])
def test_scheduler_rejects_unbounded_concurrency(parallelism: int) -> None:
    with pytest.raises(ValueError):
        evaluate_team(("55 C", "60 C", "65 C"), _stub, parallelism=parallelism)


def test_parallel_extractor_still_rejects_model_mismatch() -> None:
    def wrong(question: str) -> str:
        if "sensor: 65 C" in question:
            return "66"
        return _stub(question)

    result = evaluate_team(
        ("55 C", "60 C", "65 C"), wrong, parallelism=3
    )
    assert result.status == "rejected"
    assert result.severity is None
    assert result.errors == ("extractor_mismatch",)


def test_parallel_exception_still_rejected() -> None:
    def unreliable(question: str) -> str:
        if "sensor: 60 C" in question:
            raise RuntimeError("offline")
        return _stub(question)

    result = evaluate_team(
        ("55 C", "60 C", "65 C"), unreliable, parallelism=3
    )
    assert result.status == "rejected"
    assert result.severity is None


def test_parallel_workers_do_not_duplicate_samples() -> None:
    lock = Lock()
    captured: list[str] = []

    def counting(question: str) -> str:
        with lock:
            captured.append(question)
        return _stub(question)

    result = evaluate_team(
        ("55 C", "60 C", "65 C"), counting, parallelism=2
    )
    assert result.status == "verified"
    assert len(captured) == 4
    assert sum("Extract" in question for question in captured) == 3
    assert sum("arithmetic mean" in question for question in captured) == 1
