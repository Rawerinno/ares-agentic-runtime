"""Offline benchmark tests without Ollama running."""

import json
from typing import cast

from _pytest.capture import CaptureFixture

from ares.evaluation.ollama_benchmark import SCENARIOS, benchmark, run


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
