"""Deterministic Phase 5 acquisition acceptance gates without physical devices."""

import json

from ares.integrations.acquisition import BoundedAcquisition
from ares.integrations.acquisition_metrics import MonitoredAcquisition


def acquisition_acceptance() -> dict[str, object]:
    """Exercise success, failure, recovery and measurement in one offline fixture."""
    frames: list[bytes | BaseException] = [
        TimeoutError(),
        b"{malformed",
        json.dumps(
            {"device_id": "fixture", "step": 0, "temperature_c": 24, "healthy": True}
        ).encode(),
        json.dumps(
            {"device_id": "fixture", "step": 1, "temperature_c": 27, "healthy": False}
        ).encode(),
    ]

    def receive(_: float) -> bytes:
        item = frames.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    monitor = MonitoredAcquisition(BoundedAcquisition(receive, timeout_s=0.2))
    results = [monitor.read() for _ in range(4)]
    stats = monitor.stats()
    checks = {
        "timeout_is_rejected": results[0].error_code == "acquisition_timeout",
        "malformed_is_rejected": results[1].error_code == "acquisition_invalid_json",
        "recovery_at_expected_sequence": (
            results[2].snapshot is not None and results[2].snapshot.step == 0
        ),
        "unhealthy_is_observed_not_masked": (
            results[3].snapshot is not None and results[3].snapshot.healthy is False
        ),
        "metrics_are_consistent": (
            stats.attempts == 4
            and stats.successful == 2
            and stats.failed == 2
            and stats.max_consecutive_failures == 2
        ),
    }
    return {
        "phase": 5,
        "mode": "offline-read-only",
        "checks": checks,
        "passed": sum(checks.values()),
        "total": len(checks),
        "hardware_validated": False,
        "actuation_enabled": False,
    }
