"""Safety, trend semantics and bounded evaluation of evidence-first triage."""

import json
from pathlib import Path
from typing import cast

import pytest
from pytest import CaptureFixture

from ares.runtime.evidence_acceptance import evaluate_evidence, run
from ares.runtime.evidence_advisor import bounded_followup, parse_followup, reference_followup
from ares.runtime.temporal_evidence import (
    EvidenceReading,
    EvidenceState,
    analyze_evidence,
)


@pytest.mark.parametrize(
    ("readings", "expected"),
    [
        ([EvidenceReading(0, 20.0)], EvidenceState.INSUFFICIENT_HISTORY),
        ([EvidenceReading(0, 85.0)], EvidenceState.INSUFFICIENT_HISTORY),
        (
            [EvidenceReading(0, 20.0), EvidenceReading(1, 23.0), EvidenceReading(2, 25.0)],
            EvidenceState.RISING_TEMPERATURE,
        ),
        (
            [EvidenceReading(0, 20.0), EvidenceReading(1, 26.0), EvidenceReading(2, 20.0)],
            EvidenceState.NO_CONFIRMED_RISE,
        ),
        (
            [EvidenceReading(0, 20.0), EvidenceReading(1, float("nan"))],
            EvidenceState.INVALID_TELEMETRY,
        ),
        (
            [EvidenceReading(0, 20.0), EvidenceReading(1, 24.0, False)],
            EvidenceState.INVALID_TELEMETRY,
        ),
    ],
)
def test_evidence_never_infers_cause_from_single_reading(
    readings: list[EvidenceReading], expected: EvidenceState
) -> None:
    report = analyze_evidence(readings)
    assert report.state is expected
    assert report.device_actions == "disabled"
    assert report.suggested_followup in (
        "validate_sensor",
        "collect_more_samples",
        "inspect_thermal_system",
        "continue_monitoring",
    )


@pytest.mark.parametrize(
    "readings",
    [
        [],
        [EvidenceReading(0, 20.0), EvidenceReading(0, 21.0)],
        [EvidenceReading(1, 20.0), EvidenceReading(0, 21.0)],
        [EvidenceReading(-1, 20.0)],
        [EvidenceReading(i, 20.0) for i in range(33)],
    ],
)
def test_invalid_history_is_rejected(readings: list[EvidenceReading]) -> None:
    with pytest.raises(ValueError):
        analyze_evidence(readings)


@pytest.mark.parametrize("threshold", [0.0, float("nan"), float("inf"), -1.0])
def test_invalid_threshold_is_rejected(threshold: float) -> None:
    with pytest.raises(ValueError):
        analyze_evidence([EvidenceReading(0, 20.0)], rise_threshold_c=threshold)


def test_recommendation_parser_rejects_wrong_and_extra_fields() -> None:
    report = analyze_evidence([EvidenceReading(0, 85.0)])
    assert parse_followup(reference_followup(report), report) == (True, "accepted")
    assert parse_followup('{"followup":"inspect_thermal_system"}', report) == (
        False,
        "policy_mismatch",
    )
    assert parse_followup('{"followup":"collect_more_samples","execute":true}', report) == (
        False,
        "invalid_fields",
    )
    assert parse_followup('{"followup":"disable_safety"}', report) == (False, "invalid_value")
    assert parse_followup("unsafe arbitrary text", report) == (False, "invalid_json")


def test_offline_evidence_acceptance(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    report = evaluate_evidence(reference_followup)
    assert report["evidence_correct"] == 9
    assert report["model_accepted"] == 9
    assert report["device_actions"] == "disabled"
    target = tmp_path / "evidence-report.json"
    assert run(["--output", str(target)]) == 0
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved == json.loads(capsys.readouterr().out)


def test_model_failure_is_reported_not_masked() -> None:
    def fail(_report: object) -> str:
        raise RuntimeError("secret in provider error")

    report = evaluate_evidence(fail)
    assert report["evidence_correct"] == 9
    assert report["model_accepted"] == 0
    assert report["model_errors"] == 9
    assert "secret" not in json.dumps(report)


def test_confusion_matrix_distinguishes_untrusted_wrong_but_allowed_followup() -> None:
    def wrong(_report: object) -> str:
        return '{"followup":"collect_more_samples"}'

    report = evaluate_evidence(wrong)
    matrix = report["followup_confusion"]
    assert isinstance(matrix, dict)
    assert matrix["collect_more_samples"] == {"collect_more_samples": 3}
    assert matrix["continue_monitoring"] == {"collect_more_samples": 3}
    assert matrix["validate_sensor"] == {"collect_more_samples": 2}
    assert matrix["inspect_thermal_system"] == {"collect_more_samples": 1}
    assert report["model_accepted"] == 3


def test_confusion_redacts_untrusted_output() -> None:
    secret = "untrusted_private_token"

    def injected(_report: object) -> str:
        return '{"followup":"validate_sensor","payload":"' + secret + '"}'

    report = evaluate_evidence(injected)
    assert report["model_accepted"] == 0
    results = report["results"]
    assert isinstance(results, list)
    assert all(
        row.get("bounded_proposal") == "validate_sensor"
        for row in cast("list[dict[str, object]]", results)
    )
    assert secret not in json.dumps(report)
    assert bounded_followup("not json " + secret) == "unrecognized"
    assert bounded_followup('{"followup":"unauthorized_operation"}') == "unrecognized"
