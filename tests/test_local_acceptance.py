"""Offline acceptance tests: synthetic LLMs, no Ollama or paid services."""

from decimal import Decimal

import pytest

from ares.evaluation.local_acceptance import CASES, Case, run_suite


def good_generator(prompt: str) -> str:
    if prompt.startswith("Extract the Celsius reading"):
        return prompt.split("sensor: ", 1)[1].split(" C", 1)[0]
    if prompt.startswith("Compute the arithmetic mean"):
        payload = prompt.split("readings: ", 1)[1].split(". Return only the number.", 1)[0]
    elif prompt.startswith("Independently calculate"):
        payload = prompt.split("measurements: ", 1)[1].split(". Return only the number.", 1)[0]
    else:
        raise ValueError("unrecognized prompt")
    numbers = [Decimal(v.strip()) for v in payload.split(",")]
    return str(sum(numbers, Decimal(0)) / Decimal(len(numbers)))


def test_all_cases_complete_with_independent_reviewer() -> None:
    report = run_suite(good_generator, repeats=2)
    assert report["total_scenarios"] == len(CASES) * 2
    assert report["passed_scenarios"] == len(CASES) * 2
    assert report["failed_scenarios"] == 0
    roles = report["roles"]
    assert isinstance(roles, dict)
    assert roles["extractor"]["attempted"] == 3 * len(CASES) * 2
    assert roles["arithmetic"]["attempted"] == len(CASES) * 2
    assert roles["independent_reviewer"]["attempted"] == len(CASES) * 2


def test_wrong_arithmetic_is_rejected_without_third_role() -> None:
    def wrong(prompt: str) -> str:
        if prompt.startswith("Compute"):
            return "999"
        return good_generator(prompt)

    report = run_suite(wrong, repeats=2, cases=(CASES[0],))
    assert report["failed_scenarios"] == 2
    roles = report["roles"]
    assert isinstance(roles, dict)
    assert roles["arithmetic"]["correct"] == 0
    assert roles["independent_reviewer"]["attempted"] == 0


def test_independent_disagreement_counts_as_failure() -> None:
    def wrong_review(prompt: str) -> str:
        if prompt.startswith("Independently"):
            return "999"
        return good_generator(prompt)

    report = run_suite(wrong_review, repeats=1, cases=(CASES[0],))
    assert report["failed_scenarios"] == 1
    roles = report["roles"]
    assert isinstance(roles, dict)
    assert roles["independent_reviewer"]["accuracy"] == 0


def test_transport_error_is_counted_as_error() -> None:
    def failed(prompt: str) -> str:
        if "Extract" in prompt:
            raise RuntimeError("offline")
        return good_generator(prompt)

    report = run_suite(failed, repeats=1, cases=(CASES[0],))
    assert report["failed_scenarios"] == 1
    roles = report["roles"]
    assert isinstance(roles, dict)
    assert roles["extractor"]["errors"] == 3
    assert roles["arithmetic"]["attempted"] == 0


def test_non_repeated_case_and_invalid_bounds() -> None:
    with pytest.raises(ValueError):
        run_suite(good_generator, repeats=0)
    with pytest.raises(ValueError):
        run_suite(good_generator, cases=())
    duplicate = (Case("duplicate", ("1", "2", "3"), "2", "normal"),) * 2
    with pytest.raises(ValueError):
        run_suite(good_generator, cases=duplicate)
