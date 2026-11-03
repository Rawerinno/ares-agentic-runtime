"""Offline regression tests for paired three-agent live report comparison."""

import json
from pathlib import Path
from typing import cast

import pytest
from pytest import CaptureFixture

from ares.runtime.compare_three_agent_acceptance import compare_reports, run


def report(
    accepted: tuple[bool, bool], safe: tuple[bool, bool] = (True, True)
) -> dict[str, object]:
    return {
        "scope": "governed_three_roles",
        "role_contract": "role_only",
        "model_source": "live_ollama",
        "safety_authority": "deterministic_supervisor",
        "device_actions": "disabled",
        "total_runs": 2,
        "governed_correct": sum(safe),
        "full_team_accepted": sum(accepted),
        "results": [
            {
                "scenario": "normal_low",
                "repeat": 1,
                "severity": "normal",
                "expected_hypothesis": "stable",
                "governed_safe": safe[0],
                "team_accepted": accepted[0],
            },
            {
                "scenario": "critical_high",
                "repeat": 1,
                "severity": "critical",
                "expected_hypothesis": "thermal_load",
                "governed_safe": safe[1],
                "team_accepted": accepted[1],
            },
        ],
    }


def test_quality_regression_rejected() -> None:
    comparison = compare_reports(report((True, True)), report((True, False)))
    assert comparison["team_delta"] == -1
    assert comparison["lost"] == ["critical_high#1"]
    assert comparison["recommendation"] == "reject_quality_regression"


def test_safety_regression_rejected_even_if_team_improves() -> None:
    comparison = compare_reports(
        report((False, False)),
        report((True, True), safe=(False, True)),
    )
    assert comparison["recommendation"] == "reject_safety_regression"
    assert comparison["safety_regression"] is True


def test_equal_result_is_not_proof_of_reliability() -> None:
    comparison = compare_reports(report((True, False)), report((True, False)))
    assert comparison["recommendation"] == "insufficient_evidence_for_general_reliability"


@pytest.mark.parametrize("mutation", ["duplicate", "count", "scenario", "scope", "device"])
def test_malformed_comparisons_fail_closed(mutation: str) -> None:
    baseline = report((True, False))
    candidate = report((True, False))
    rows = cast("list[dict[str, object]]", candidate["results"])
    if mutation == "duplicate":
        rows[1]["scenario"] = "normal_low"
    elif mutation == "count":
        candidate["governed_correct"] = 99
    elif mutation == "scenario":
        rows[0]["expected_hypothesis"] = "sensor_fault"
    elif mutation == "scope":
        candidate["scope"] = "other"
    else:
        candidate["device_actions"] = "enabled"
    with pytest.raises(ValueError):
        compare_reports(baseline, candidate)


def test_cli_writes_report_and_returns_regression_status(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    output = tmp_path / "comparison.json"
    baseline.write_text(json.dumps(report((True, True))), encoding="utf-8")
    candidate.write_text(json.dumps(report((True, False))), encoding="utf-8")
    code = run(
        ["--baseline", str(baseline), "--candidate", str(candidate), "--output", str(output)]
    )
    assert code == 1
    assert json.loads(output.read_text(encoding="utf-8")) == json.loads(capsys.readouterr().out)
