"""Three-agent acceptance differentiates raw role success from governed safety."""

import json
from pathlib import Path

import pytest
from pytest import CaptureFixture

from ares.runtime.governed_three_agents import reference_generate
from ares.runtime.three_agent_acceptance import (
    SCENARIOS,
    Scenario,
    evaluate_three_roles,
    run,
)


def test_offline_reference_three_role_acceptance(tmp_path: Path) -> None:
    report = evaluate_three_roles(reference_generate, tmp_path, repeats=2)
    assert report["total_runs"] == 18
    assert report["governed_correct"] == 18
    assert report["full_team_accepted"] == 18
    assert report["idempotent_replays"] == 18
    assert report["rejection_counts"] == {"investigator": {}, "planner": {}, "critic": {}}
    stats = report["role_metrics"]
    assert isinstance(stats, dict)
    for role in ("investigator", "planner", "critic"):
        assert stats[role]["attempted"] == 18
        assert stats[role]["accepted"] == 18
        assert stats[role]["errors"] == 0


def test_invalid_investigator_fails_closed_and_skips_other_agents(tmp_path: Path) -> None:
    def unsafe(_question: str) -> str:
        return '{"hypothesis":"stable","severity":"normal"}'

    report = evaluate_three_roles(unsafe, tmp_path, repeats=2, scenarios=(SCENARIOS[4],))
    assert report["governed_correct"] == 2
    assert report["full_team_accepted"] == 0
    stats = report["role_metrics"]
    assert isinstance(stats, dict)
    assert stats["investigator"]["attempted"] == 2
    assert stats["investigator"]["accepted"] == 0
    assert stats["planner"]["attempted"] == 0
    assert stats["critic"]["attempted"] == 0
    assert report["rejection_counts"]["investigator"] == {"policy_mismatch:severity_mismatch": 2}
    assert report["idempotent_replays"] == 2


def test_model_unavailable_still_preserves_governed_safety(tmp_path: Path) -> None:
    def offline(_question: str) -> str:
        raise RuntimeError("private-provider-token")

    report = evaluate_three_roles(offline, tmp_path, repeats=1, scenarios=(SCENARIOS[7],))
    assert report["governed_correct"] == 1
    assert report["full_team_accepted"] == 0
    stats = report["role_metrics"]
    assert isinstance(stats, dict)
    assert stats["investigator"]["errors"] == 1
    assert "private-provider-token" not in str(report)


def test_reference_includes_invalid_sensor_critical(tmp_path: Path) -> None:
    report = evaluate_three_roles(
        reference_generate, tmp_path, repeats=1, scenarios=(SCENARIOS[-1],)
    )
    assert report["governed_correct"] == 1
    assert report["full_team_accepted"] == 1


@pytest.mark.parametrize("repeats", [0, 6])
def test_invalid_repetition_count_is_rejected(tmp_path: Path, repeats: int) -> None:
    with pytest.raises(ValueError):
        evaluate_three_roles(reference_generate, tmp_path, repeats=repeats)


def test_duplicate_scenario_names_are_rejected(tmp_path: Path) -> None:
    duplicates = (
        Scenario("duplicate", 20.0, "normal"),
        Scenario("duplicate", 85.0, "critical"),
    )
    with pytest.raises(ValueError):
        evaluate_three_roles(reference_generate, tmp_path, scenarios=duplicates)


def test_cli_json_offline_has_correct_scope(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    destination = tmp_path / "acceptance.json"
    assert run(["--repeats", "1", "--output", str(destination)]) == 0
    report = json.loads(destination.read_text(encoding="utf-8"))
    assert report == json.loads(capsys.readouterr().out)
    assert report["model_source"] == "offline_reference"
    assert report["total_runs"] == 9
    assert report["device_actions"] == "disabled"
