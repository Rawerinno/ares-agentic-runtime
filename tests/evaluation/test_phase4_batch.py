"""Offline batch validations."""

from typing import cast

from ares.evaluation.phase4_batch import validate


def test_offline_batch() -> None:
    report = validate(repeats=2)
    assert report["passed"] == report["total"] == 6
    assert report["scenario_count"] == 12
    checks = cast("dict[str, bool]", report["checks"])
    assert checks["audit_two_event_roundtrip"] is True
    assert checks["mocked_degraded_fallback"] is True
    assert checks["no_rejected_responses"] is True
    assert report["governed_correct"] == 12
    assert report["model_errors"] == 0
    assert report["rejected_responses"] == 0
    assert isinstance(report["latency_mean_ms"], float)
    assert isinstance(report["latency_median_ms"], float)
