"""Offline benchmark tests without Ollama running."""

import json
from typing import cast

from _pytest.capture import CaptureFixture
from pytest import MonkeyPatch

from ares.evaluation.ollama_benchmark import SCENARIOS, benchmark, run
from ares.intelligence.resilience import BoundedProposalEngine, OutcomeStatus, ProposalOutcome
from ares.supervisor import Assessment


def test_reference_model_passes_all_scenarios() -> None:
    report = benchmark()
    assert report["mode"] == "offline-reference"
    assert report["passed"] == len(SCENARIOS)
    assert report["total"] == len(SCENARIOS)
    cases = cast("list[dict[str, object]]", report["cases"])
    assert isinstance(cases, list)
    assert all(case["passed"] is True for case in cases)


def test_cli_emits_machine_readable_json(capsys: CaptureFixture[str]) -> None:
    assert run([]) == 0
    report: dict[str, object] = json.loads(capsys.readouterr().out)
    assert report["total"] == 6
    assert report["passed"] == 6


def test_normal_scenario_requires_observe() -> None:
    report = benchmark()
    cases = cast("list[dict[str, object]]", report["cases"])
    assert cases[0]["expected_proposal"] == "observe"
    assert cases[2]["expected_proposal"] == "investigate"
    assert cases[4]["expected_proposal"] == "request_review"


def test_repeated_benchmark_isolated_cases() -> None:
    report = benchmark(repeats=3)
    assert report["total"] == 18
    assert report["passed"] == 18
    assert report["governed_passed"] == 18
    assert report["repeats"] == 3
    assert report["model_error_count"] == 0
    cases = cast("list[dict[str, object]]", report["cases"])
    assert [case["repeat"] for case in cases] == [1] * 6 + [2] * 6 + [3] * 6


def test_repeats_validation() -> None:
    import pytest

    with pytest.raises(ValueError, match="repeats"):
        benchmark(repeats=0)
    with pytest.raises(ValueError, match="repeats"):
        benchmark(repeats=21)


def test_model_errors_still_count_governed_fallback(monkeypatch: MonkeyPatch) -> None:
    def fail(self: BoundedProposalEngine, assessment: Assessment) -> ProposalOutcome:
        return ProposalOutcome(OutcomeStatus.MODEL_ERROR, None, "model_exception", 2.0)

    monkeypatch.setattr(BoundedProposalEngine, "evaluate", fail)
    report = benchmark()
    assert report["passed"] == 0
    assert report["governed_passed"] == 6
    assert report["model_error_count"] == 6
    cases = cast("list[dict[str, object]]", report["cases"])
    assert all(case["governance_mode"] == "deterministic_degraded" for case in cases)
