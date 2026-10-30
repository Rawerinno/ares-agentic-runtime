"""Acquisition metrics are deterministic and have no active recovery side effects."""

import json

from ares.integrations.acquisition import BoundedAcquisition
from ares.integrations.acquisition_metrics import MonitoredAcquisition


def packet(step: int) -> bytes:
    return json.dumps(
        {"device_id": "x", "step": step, "temperature_c": 21.0, "healthy": True}
    ).encode()


def test_metrics_capture_failure_streaks_and_recovery() -> None:
    frames: list[bytes | BaseException] = [
        TimeoutError(),
        b"invalid",
        packet(0),
        OSError("unplugged"),
        packet(1),
    ]

    def receive(_: float) -> bytes:
        item = frames.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    monitor = MonitoredAcquisition(BoundedAcquisition(receive))
    assert monitor.stats().attempts == 0
    for _ in range(5):
        monitor.read()
    stats = monitor.stats()
    assert stats.attempts == 5
    assert stats.successful == 2
    assert stats.failed == 3
    assert stats.consecutive_failures == 0
    assert stats.max_consecutive_failures == 2
    assert stats.error_counts == {
        "acquisition_timeout": 1,
        "acquisition_invalid_json": 1,
        "acquisition_transport_error": 1,
    }


def test_snapshot_is_immutable_from_external_mutations() -> None:
    monitored = MonitoredAcquisition(BoundedAcquisition(lambda _: packet(0)))
    monitored.read()
    snapshot = monitored.stats()
    snapshot.error_counts["fabricated"] = 100
    assert monitored.stats().error_counts == {}
