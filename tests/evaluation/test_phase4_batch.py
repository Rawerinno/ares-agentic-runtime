"""Offline batch validations."""

from ares.evaluation.phase4_batch import validate


def test_offline_batch() -> None:
    report = validate(repeats=2)
    assert report["passed"] == report["total"] == 3
    assert report["scenario_count"] == 12
    assert report["governed_correct"] == 12
