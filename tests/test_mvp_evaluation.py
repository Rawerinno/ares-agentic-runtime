"""Offline ARES multi-role acceptance includes replay, recovery and authorization."""

import json
from pathlib import Path

import pytest
from pytest import CaptureFixture

from ares.runtime.mvp_evaluation import evaluate_suite, run


def test_evaluation_detects_expected_outcomes(tmp_path: Path) -> None:
    result = evaluate_suite(tmp_path, scenarios=30)
    assert result["scope"] == "offline_simulation_reference_model"
    assert result["cases"] == 30
    assert result["correct_scenarios"] == 30
    assert result["idempotent_replays"] == 30
    assert result["role_handoffs"] == 150
    assert result["malicious_proposals_rejected"] == 3
    assert result["severity_counts"] == {
        "normal": 10, "warning": 10, "critical": 10
    }
    assert result["checks_passed"] == result["checks_total"]
    assert result["passed"] is True


def test_evaluation_cli_writes_machine_readable_report(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    path = tmp_path / "mvp-report.json"
    assert run(["--scenarios", "6", "--output", str(path)]) == 0
    stored = json.loads(path.read_text(encoding="utf-8"))
    displayed = json.loads(capsys.readouterr().out)
    assert stored == displayed
    assert stored["passed"] is True
    assert stored["cases"] == 6
    assert stored["device_actions"] == "disabled"


@pytest.mark.parametrize("scenarios", [0, 2, 4, 301])
def test_evaluation_rejects_unbounded_counts(
    tmp_path: Path, scenarios: int
) -> None:
    with pytest.raises(ValueError):
        evaluate_suite(tmp_path, scenarios=scenarios)
