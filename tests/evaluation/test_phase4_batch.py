"""Offline batch validations."""

from typing import cast

from ares.evaluation.phase4_batch import validate


def test_offline_batch() -> None:
    report = validate(repeats=2)
    assert report["passed"] == report["total"] == 4
    assert report["scenario_count"] == 12
    checks = cast("dict[str, bool]", report["checks"])
    assert checks["audit_two_event_roundtrip"] is True
    assert report["governed_correct"] == 12
