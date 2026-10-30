"""Malformed but size-bounded telemetry must not escape the failure boundary."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ares.integrations.acquisition import BoundedAcquisition
from ares.integrations.acquisition_metrics import MonitoredAcquisition
from ares.integrations.recorded import RecordedSensor, RecordingError


def sample(temperature: int = 22) -> dict[str, object]:
    return dict(device_id="sensor-1", step=0, temperature_c=temperature, healthy=True)


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (json.dumps(sample(10**1000)).encode(), ("acquisition_invalid_schema",)),
        (json.dumps(sample(-(10**1000))).encode(), ("acquisition_invalid_schema",)),
        (
            b"[" * 1500 + b"0" + b"]" * 1500,
            ("acquisition_invalid_json", "acquisition_invalid_schema"),
        ),
    ],
    ids=["positive-overflow", "negative-overflow", "deep-json"],
)
def test_adversarial_frame_fails_closed_and_recovery_is_counted(
    payload: bytes, code: tuple[str, ...]
) -> None:
    assert len(payload) <= 4096
    frames = iter([payload, json.dumps(sample()).encode()])
    source = MonitoredAcquisition(BoundedAcquisition(lambda _: next(frames)))
    error = source.read().error_code
    # Parser recursion limits vary by interpreter/instrumentation. A deeply
    # nested list must fail either parsing or the exact schema check.
    assert error is not None and error in code
    recovered = source.read()
    assert recovered.snapshot is not None and recovered.snapshot.step == 0
    assert source.stats().error_counts == {error: 1}
    assert source.stats().successful == 1


@pytest.mark.parametrize("field", ["temperature_c", "timestamp_s"])
@pytest.mark.parametrize("value", [10**1000, -(10**1000)], ids=["positive", "negative"])
def test_recorded_numeric_overflow_has_structured_error(
    tmp_path: Path, field: str, value: int
) -> None:
    event = sample()
    event[field] = value
    path = tmp_path / "overflow.json"
    path.write_text(json.dumps([event]), encoding="utf-8")
    code = "recording_invalid_timestamps" if field == "timestamp_s" else "recording_invalid_types"
    with pytest.raises(RecordingError, match=code):
        RecordedSensor.from_file(path)


def test_recorded_deep_json_has_structured_error(tmp_path: Path) -> None:
    path = tmp_path / "deep.json"
    path.write_text("[" * 1500 + "0" + "]" * 1500, encoding="utf-8")
    with pytest.raises(RecordingError, match=r"^recording_invalid_(json|entry)$"):
        RecordedSensor.from_file(path)


def test_parser_recursion_failure_is_contained_in_acquisition() -> None:
    source = BoundedAcquisition(lambda _: json.dumps(sample()).encode())
    with patch("ares.integrations.acquisition.json.loads", side_effect=RecursionError):
        assert source.read().error_code == "acquisition_invalid_json"
    assert source.read().snapshot is not None


def test_parser_recursion_failure_is_contained_in_recording(tmp_path: Path) -> None:
    path = tmp_path / "sample.json"
    path.write_text(json.dumps([sample()]), encoding="utf-8")
    with (
        patch("ares.integrations.recorded.json.loads", side_effect=RecursionError),
        pytest.raises(RecordingError, match="recording_invalid_json"),
    ):
        RecordedSensor.from_file(path)
