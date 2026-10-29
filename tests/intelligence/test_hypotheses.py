"""Hypotheses are optional checks, never verified causes or actuation requests."""

from ares.intelligence.hypotheses import HypothesisStatus, suggested_checks
from ares.simulation import DeviceSnapshot
from ares.supervisor import Assessment, Severity


def assessment(severity: Severity, healthy: bool = True) -> Assessment:
    return Assessment(DeviceSnapshot("sensor", 1, 85.0, healthy), severity, "Rule", "Review")


def test_normal_reading_does_not_invent_faults() -> None:
    assert suggested_checks(assessment(Severity.NORMAL)) == ()


def test_warning_offers_unverified_non_actuating_checks() -> None:
    checks = suggested_checks(assessment(Severity.WARNING))
    assert len(checks) == 3
    assert all(check.status is HypothesisStatus.UNVERIFIED for check in checks)
    assert "calibrated" in checks[2].verification


def test_unhealthy_sensor_priority() -> None:
    checks = suggested_checks(assessment(Severity.CRITICAL, healthy=False))
    assert len(checks) == 1
    assert checks[0].title == "Sensor validity uncertain"
