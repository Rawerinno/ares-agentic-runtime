"""Acquisition recovery guarantees for transport-neutral read-only inputs."""

import json

from ares.integrations.acquisition import BoundedAcquisition


def frame(step: int, *, healthy: bool = True) -> bytes:
    return json.dumps(
        {"device_id": "sensor-1", "step": step, "temperature_c": 22.5, "healthy": healthy}
    ).encode("utf-8")


def test_recovery_after_timeout_and_malformed_frame() -> None:
    responses: list[bytes | BaseException] = [
        frame(0),
        TimeoutError(),
        b"{invalid",
        frame(1),
        frame(2, healthy=False),
    ]

    def receive(_: float) -> bytes:
        item = responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    device = BoundedAcquisition(receive)
    first = device.read()
    assert first.snapshot is not None and first.snapshot.step == 0
    assert device.read().error_code == "acquisition_timeout"
    assert device.read().error_code == "acquisition_invalid_json"
    resumed = device.read()
    assert resumed.snapshot is not None and resumed.snapshot.step == 1
    assert resumed.error_code is None
    unhealthy = device.read()
    assert unhealthy.snapshot is not None and unhealthy.snapshot.healthy is False


def test_rejected_sequence_does_not_advance() -> None:
    frames = iter((frame(0), frame(4), frame(1)))
    device = BoundedAcquisition(lambda _: next(frames))
    assert device.read().error_code is None
    assert device.read().error_code == "acquisition_invalid_sequence"
    resumed = device.read()
    assert resumed.snapshot is not None and resumed.snapshot.step == 1
