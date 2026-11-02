"""Read-only aggregate metrics retain bounded enums instead of model prose."""

import json
from pathlib import Path

from ares.runtime.governed_three_agents import reference_generate
from ares.runtime.three_agent_acceptance import (
    SCENARIOS,
    Scenario,
    evaluate_three_roles,
)


def test_offline_reference_confusion_is_diagonal(tmp_path: Path) -> None:
    report = evaluate_three_roles(
        reference_generate, tmp_path, repeats=1, role_only=True, probe_roles=True
    )
    assert report["investigator_confusion"] == {
        "stable": {"stable": 3},
        "thermal_load": {"thermal_load": 5},
        "sensor_fault": {"sensor_fault": 1},
    }


def test_wrong_hypothesis_is_captured_without_unsafe_text(tmp_path: Path) -> None:
    secret = "do_not_preserve_this_unsafe_output"

    def unsafe(question: str) -> str:
        if "ROLE=investigator." in question:
            return json.dumps({"hypothesis": "stable", "untrusted": secret})
        return reference_generate(question)

    report = evaluate_three_roles(
        unsafe, tmp_path, repeats=1, scenarios=(SCENARIOS[4],),
        role_only=True, probe_roles=True,
    )
    assert report["investigator_confusion"] == {"thermal_load": {"stable": 1}}
    assert secret not in json.dumps(report)
    assert report["governed_correct"] == 1
    assert report["full_team_accepted"] == 0


def test_custom_scenario_name_does_not_change_ground_truth(tmp_path: Path) -> None:
    report = evaluate_three_roles(
        reference_generate,
        tmp_path,
        scenarios=(Scenario("arbitrary-label", 65.0, "warning"),),
        role_only=True,
        repeats=1,
    )
    assert report["investigator_confusion"] == {"thermal_load": {"thermal_load": 1}}


def test_malformed_hypotheses_only_record_unrecognized(tmp_path: Path) -> None:
    def invalid(question: str) -> str:
        if "ROLE=investigator." in question:
            return "injected untrusted content"
        return reference_generate(question)

    report = evaluate_three_roles(
        invalid,
        tmp_path,
        scenarios=(SCENARIOS[4],),
        role_only=True,
        repeats=1,
    )
    assert report["investigator_confusion"] == {"thermal_load": {"unrecognized": 1}}
    assert "injected untrusted content" not in json.dumps(report)
