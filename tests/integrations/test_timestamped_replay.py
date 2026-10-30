"""End-to-end timestamped replay contracts remain offline and read-only."""

import json
from pathlib import Path
from typing import cast

import pytest

from ares.integrations.recorded import RecordedSensor, RecordingError
from ares.integrations.replay_cli import replay


def write(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    path = tmp_path / "timed.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def rows() -> list[dict[str, object]]:
    return [
        {"device_id": "x", "step": 0, "temperature_c": 20, "healthy": True, "timestamp_s": 0.0},
        {"device_id": "x", "step": 1, "temperature_c": 21, "healthy": True, "timestamp_s": 0.2},
        {"device_id": "x", "step": 2, "temperature_c": 22, "healthy": True, "timestamp_s": 3.0},
    ]


def test_timed_replay_reports_recorded_gap(tmp_path: Path) -> None:
    report = replay(write(tmp_path, rows()))
    findings = cast("list[dict[str, object]]", report["findings"])
    assert report["timestamps_present"] is True
    assert report["staleness_assessed"] is False
    assert {"step": 2, "code": "recorded_sampling_gap"} in findings


@pytest.mark.parametrize("bad_stamp", [float("nan"), float("inf"), -1.0, True])
def test_invalid_timestamp_rejected(tmp_path: Path, bad_stamp: object) -> None:
    samples = rows()
    samples[1]["timestamp_s"] = bad_stamp
    with pytest.raises(RecordingError):
        RecordedSensor.from_file(write(tmp_path, samples))


def test_missing_timestamp_in_middle_rejected(tmp_path: Path) -> None:
    samples = rows()
    del samples[1]["timestamp_s"]
    with pytest.raises(RecordingError, match="inconsistent_timestamps"):
        RecordedSensor.from_file(write(tmp_path, samples))


def test_legacy_recordings_still_work(tmp_path: Path) -> None:
    samples = rows()
    for sample in samples:
        del sample["timestamp_s"]
    result = replay(write(tmp_path, samples))
    assert result["timestamps_present"] is False
    assert result["staleness_assessed"] is False
