"""Offline concurrency policy tests; no model, network or hardware required."""

from collections.abc import Mapping

import pytest

from ares.evaluation.concurrency_policy import choose_concurrency


def sample(candidate: int = 2, speedup: float = 1.3) -> Mapping[str, object]:
    return {
        "model_scope": "raw_model_only",
        "parallelism": candidate,
        "sequential": {
            "total": 18,
            "correct": 18,
            "accuracy": 1.0,
            "error_count": 0,
            "wall_time_ms": 18000.0,
        },
        "parallel": {
            "total": 18,
            "correct": 18,
            "accuracy": 1.0,
            "error_count": 0,
            "wall_time_ms": 18000.0 / speedup,
        },
    }


def test_default_is_sequential_without_evidence() -> None:
    decision = choose_concurrency([], candidate=2)
    assert decision.parallelism == 1
    assert not decision.authorized
    assert decision.reason == "insufficient_evidence"


def test_single_good_run_does_not_authorize_parallelism() -> None:
    decision = choose_concurrency([sample(candidate=3)], candidate=3)
    assert decision.parallelism == 1
    assert decision.accepted_trials == 1
    assert decision.reason == "insufficient_trials"


def test_three_good_reproducible_runs_allow_only_requested_parallelism() -> None:
    decision = choose_concurrency(
        [sample(speedup=1.2), sample(speedup=1.3), sample(speedup=1.4)],
        candidate=2,
    )
    assert decision.parallelism == 2
    assert decision.authorized
    assert decision.reason == "evidence_threshold_met"
    assert decision.median_speedup == 1.3


def test_any_slow_run_rejects_even_when_median_is_fast() -> None:
    decision = choose_concurrency(
        [sample(speedup=1.3), sample(speedup=0.786), sample(speedup=1.5)],
        candidate=2,
    )
    assert decision.parallelism == 1
    assert decision.reason == "speedup_not_reproducible"


def test_error_or_incorrect_answer_rejects_all_trials() -> None:
    faulty = dict(sample())
    faulty["parallel"] = {
        "total": 18,
        "correct": 17,
        "accuracy": 0.9444,
        "error_count": 0,
        "wall_time_ms": 10000.0,
    }
    decision = choose_concurrency([sample(speedup=1.2), faulty, sample(speedup=1.4)], candidate=2)
    assert decision.parallelism == 1
    assert decision.reason == "invalid_or_incorrect_trial"


def test_incomparable_task_counts_rejected() -> None:
    mismatched = dict(sample())
    mismatched["sequential"] = {
        "total": 12,
        "correct": 12,
        "accuracy": 1.0,
        "error_count": 0,
        "wall_time_ms": 18000.0,
    }
    mismatched["parallel"] = {
        "total": 12,
        "correct": 12,
        "accuracy": 1.0,
        "error_count": 0,
        "wall_time_ms": 10000.0,
    }
    decision = choose_concurrency(
        [sample(speedup=1.2), sample(speedup=1.4), mismatched],
        candidate=2,
    )
    assert decision.reason == "incomparable_task_counts"
    assert decision.parallelism == 1


@pytest.mark.parametrize("candidate", [0, 1, 5])
def test_invalid_candidate(candidate: int) -> None:
    with pytest.raises(ValueError):
        choose_concurrency([], candidate=candidate)


def test_boolean_is_not_a_valid_count() -> None:
    invalid = dict(sample())
    invalid["parallel"] = {
        "total": True,
        "correct": True,
        "accuracy": 1.0,
        "error_count": 0,
        "wall_time_ms": 10000.0,
    }
    decision = choose_concurrency([invalid, sample(speedup=1.2), sample(speedup=1.4)], candidate=2)
    assert decision.reason == "invalid_or_incorrect_trial"


def test_duplicate_reports_do_not_count_as_independent_trials() -> None:
    repeated = sample(speedup=1.4)
    decision = choose_concurrency([repeated, repeated, repeated], candidate=2)
    assert decision.parallelism == 1
    assert decision.reason == "duplicate_trial"


def test_governed_accuracy_cannot_authorize_parallelism() -> None:
    result = dict(sample())
    result["model_scope"] = "governed"
    decision = choose_concurrency([result, sample(speedup=1.2)], candidate=2)
    assert decision.reason == "invalid_or_incorrect_trial"
