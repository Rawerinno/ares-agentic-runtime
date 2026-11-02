"""Offline release gate regression tests (no Ollama, network or devices)."""

import json
from pathlib import Path

from pytest import CaptureFixture

from ares.evaluation.release_acceptance import acceptance_report, run


def test_acceptance_is_deterministic_and_all_scenarios_pass() -> None:
    result = acceptance_report()
    assert result["scope"] == "offline_stub_only"
    assert result["scenario_count"] == 121
    assert result["simulated_model_calls"] == 484
    assert result["audit_entries_checked"] == 121
    assert result["default_parallelism"] == 1
    assert result["all_passed"] is True
    checks = result["checks"]
    assert isinstance(checks, dict)
    assert checks["extreme_input_rejected"] is True
    assert checks["arithmetic_fail_closed"] is True
    assert checks["provider_failure_fail_closed"] is True


def test_acceptance_cli_generates_json_report(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    output = tmp_path / "report.json"
    assert run(["--output", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["all_passed"] is True
    assert report == json.loads(capsys.readouterr().out)
