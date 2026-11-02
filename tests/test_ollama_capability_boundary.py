"""Offline tests for the staged raw-model capability boundary."""

from typing import cast

from ares.evaluation.ollama_capability_boundary import PROBES, evaluate


def test_all_correct_reaches_last_tier() -> None:
    answers = {probe.question: probe.expected for probe in PROBES}
    report = evaluate(lambda question: answers[question], repeats=3)
    assert report["highest_passing_tier"] == 3
    assert report["stopped_at_tier"] is None


def test_failure_stops_before_harder_probes() -> None:
    seen: list[str] = []

    def bad_first_tier(question: str) -> str:
        seen.append(question)
        return "wrong"

    report = evaluate(bad_first_tier, repeats=3)
    assert report["highest_passing_tier"] == 0
    assert report["stopped_at_tier"] == 1
    assert len(seen) == 9
    assert all(question in {p.question for p in PROBES if p.tier == 1} for question in seen)


def test_inconsistent_answers_fail_even_at_reasonable_accuracy() -> None:
    calls: dict[str, int] = {}

    def variable(question: str) -> str:
        calls[question] = calls.get(question, 0) + 1
        expected = next(p.expected for p in PROBES if p.question == question)
        if question == PROBES[0].question and calls[question] == 3:
            return "wrong"
        return expected

    report = evaluate(variable, repeats=3, min_accuracy=0.80)
    assert report["highest_passing_tier"] == 0
    first = cast("list[dict[str, object]]", report["tiers"])[0]
    assert first["all_consistent"] is False
    assert cast("float", first["accuracy"]) > 0.80


def test_model_exceptions_are_failures_not_governed_success() -> None:
    def unavailable(_question: str) -> str:
        raise RuntimeError("model unavailable")

    report = evaluate(unavailable, repeats=2)
    assert report["highest_passing_tier"] == 0
    assert cast("list[dict[str, object]]", report["tiers"])[0]["accuracy"] == 0
    assert report["model_scope"] == "raw_model_only"


def test_invalid_parameters_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        evaluate(lambda _: "20", repeats=1)
    with pytest.raises(ValueError):
        evaluate(lambda _: "20", min_accuracy=0)


def test_numeric_equivalence_not_penalized() -> None:
    answers = {probe.question: probe.expected for probe in PROBES}
    answers[PROBES[3].question] = "20.0"
    answers[PROBES[4].question] = "6e1"
    answers[PROBES[5].question] = "85.00"
    report = evaluate(lambda question: answers[question], repeats=3)
    assert report["highest_passing_tier"] == 3
    tier_two = cast("list[dict[str, object]]", report["tiers"])[1]
    assert tier_two["accuracy"] == 1.0


def test_equivalent_numeric_formatting_counts_as_consistent() -> None:
    answers = {probe.question: probe.expected for probe in PROBES}
    count: dict[str, int] = {}

    def generator(question: str) -> str:
        count[question] = count.get(question, 0) + 1
        if question == PROBES[3].question:
            return ("20", "20.0", "2e1")[count[question] - 1]
        return answers[question]

    report = evaluate(generator)
    assert report["highest_passing_tier"] == 3
    tier_two = cast("list[dict[str, object]]", report["tiers"])[1]
    rows = cast("list[dict[str, object]]", tier_two["cases"])
    assert rows[0]["consistent"] is True


def test_invalid_numeric_answer_is_not_accepted() -> None:
    answers = {probe.question: probe.expected for probe in PROBES}
    answers[PROBES[0].question] = "NaN"
    report = evaluate(lambda question: answers[question])
    assert report["highest_passing_tier"] == 0


def test_wrong_numeric_answer_still_fails() -> None:
    answers = {probe.question: probe.expected for probe in PROBES}
    answers[PROBES[3].question] = "21"
    report = evaluate(lambda question: answers[question])
    assert report["highest_passing_tier"] == 1
    assert report["stopped_at_tier"] == 2
