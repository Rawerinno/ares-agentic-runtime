"""Fail the acceptance run when any acquisition safety gate regresses."""

from typing import cast

from ares.evaluation.phase5_acquisition_acceptance import acquisition_acceptance


def test_phase5_acquisition_offline_acceptance() -> None:
    report = acquisition_acceptance()
    assert report["passed"] == report["total"] == 6
    checks = cast("dict[str, bool]", report["checks"])
    assert all(checks.values())
    assert report["hardware_validated"] is False
    assert report["actuation_enabled"] is False
