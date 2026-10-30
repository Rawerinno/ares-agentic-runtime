"""Acceptance gates remain offline and avoid claiming certification."""

from ares.evaluation.phase4_acceptance import phase4_acceptance


def test_offline_gates_pass_and_live_validation_remains_required() -> None:
    report = phase4_acceptance()
    assert report["passed"] == report["total"] == 3
    assert report["scope"] == "offline-only"
    assert report["live_validation_required"] is True
    assert report["hardware_safety_certified"] is False
