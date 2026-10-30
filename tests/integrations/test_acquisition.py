"""Transport-neutral, fail-closed acquisition tests."""

import json

import pytest

from ares.integrations.acquisition import BoundedAcquisition


def frame(step: int = 0, device_id: str = "sensor-1") -> bytes:
    return json.dumps(
        {"device_id": device_id, "step": step, "temperature_c": 24.5, "healthy": True}
    ).encode()


def test_valid_frames_preserve_order() -> None:
    frames = iter((frame(0), frame(1)))
    acquisition = BoundedAcquisition(lambda _: next(frames))
    first = acquisition.read()
    second = acquisition.read()
    assert first.error_code is None
    assert first.snapshot is not None and first.snapshot.step == 0
    assert second.snapshot is not None and second.snapshot.step == 1


def test_timeout_keeps_sequence_position() -> None:
    attempts = iter((None, frame()))

    def receive(timeout: float) -> bytes:
        assert timeout == 0.5
        value = next(attempts)
        if value is None:
            raise TimeoutError
        return value

    acquisition = BoundedAcquisition(receive, timeout_s=0.5)
    assert acquisition.read().error_code == "acquisition_timeout"
    assert acquisition.read().snapshot is not None


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"", "acquisition_invalid_frame"),
        (b" " * 4097, "acquisition_invalid_frame"),
        (b"not-json", "acquisition_invalid_json"),
        (b'{"step":0,"step":1}', "acquisition_invalid_json"),
        (
            b'{"device_id":"x","step":0,"temperature_c":NaN,"healthy":true}',
            "acquisition_invalid_json",
        ),
        (b"[]", "acquisition_invalid_schema"),
        (b'{"device_id":"x","step":0,"temperature_c":23}', "acquisition_invalid_schema"),
        (frame(1), "acquisition_invalid_sequence"),
    ],
)
def test_rejected_frames(payload: bytes, code: str) -> None:
    assert BoundedAcquisition(lambda _: payload).read().error_code == code


def test_device_change_is_rejected() -> None:
    frames = iter((frame(), frame(1, "other")))
    acquisition = BoundedAcquisition(lambda _: next(frames))
    assert acquisition.read().error_code is None
    assert acquisition.read().error_code == "acquisition_invalid_sequence"


def test_transport_failure_is_rejected() -> None:
    def broken(_: float) -> bytes:
        raise OSError("disconnected")

    assert BoundedAcquisition(broken).read().error_code == "acquisition_transport_error"


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_timeout_configuration_rejected(timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout_s"):
        BoundedAcquisition(lambda _: frame(), timeout_s=timeout)
