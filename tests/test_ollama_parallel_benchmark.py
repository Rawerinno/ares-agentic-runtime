"""Offline checks of independent sequential and parallel model calls."""

from decimal import Decimal

import pytest

from ares.evaluation.ollama_parallel_benchmark import WorkItem, benchmark, correct


def test_numeric_grading_is_exact_and_finite() -> None:
    assert correct("20.0", Decimal("20"))
    assert correct("2e1", Decimal("20"))
    assert not correct("NaN", Decimal("20"))
    assert not correct("Infinity", Decimal("20"))
    assert not correct("about 20", Decimal("20"))
    assert not correct("21", Decimal("20"))


def test_parallel_results_are_verified_independently() -> None:
    cases = (
        WorkItem("a", "first", Decimal("20")),
        WorkItem("b", "second", Decimal("-5")),
    )
    answers = {"first": "20.0", "second": "-5"}
    report = benchmark(lambda prompt: answers[prompt], cases=cases, repeats=2)
    assert report["task_count_per_mode"] == 4
    sequential = report["sequential"]
    parallel = report["parallel"]
    assert isinstance(sequential, dict) and isinstance(parallel, dict)
    assert sequential["correct"] == 4
    assert parallel["correct"] == 4
    assert sequential["accuracy"] == 1.0
    assert parallel["accuracy"] == 1.0


def test_model_errors_do_not_pass() -> None:
    cases = (WorkItem("a", "first", Decimal("20")),)

    def failed(_prompt: str) -> str:
        raise RuntimeError("offline")

    report = benchmark(failed, cases=cases, repeats=2)
    for key in ("sequential", "parallel"):
        result = report[key]
        assert isinstance(result, dict)
        assert result["accuracy"] == 0
        assert result["error_count"] == 2


@pytest.mark.parametrize(
    ("parallelism", "repeats"),
    [(0, 2), (9, 2), (3, 0), (3, 11)],
)
def test_reject_invalid_limits(parallelism: int, repeats: int) -> None:
    with pytest.raises(ValueError):
        benchmark(lambda _: "20", parallelism=parallelism, repeats=repeats)


def test_no_tasks_is_rejected() -> None:
    with pytest.raises(ValueError):
        benchmark(lambda _: "20", cases=())
