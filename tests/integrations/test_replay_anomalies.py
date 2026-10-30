"""Recorded replay findings are deterministic and not live alarms."""

import json
from pathlib import Path
from typing import cast

import pytest

from ares.integrations.replay_anomalies import analyze_recording
from ares.integrations.replay_cli import replay
from ares.simulation import DeviceSnapshot


def test_jump_and_health_findings(tmp_path: Path) -> None:
    path = tmp_path / "recording.json"
    path.write_text(
        json.dumps(
            [
                {"device_id": "x", "step": 0, "temperature_c": 20, "healthy": True},
                {"device_id": "x", "step": 1, "temperature_c": 20, "healthy": True},
                {"device_id": "x", "step": 2, "temperature_c": 65, "healthy": False},
            ]
        ),
        encoding="utf-8",
    )
    report = replay(path)
    findings = cast("list[dict[str, object]]", report["findings"])
    assert {finding["code"] for finding in findings} == {"sensor_unhealthy", "temperature_jump"}
    assert all(finding["step"] == 2 for finding in findings)
    assert report["staleness_assessed"] is False


def test_identical_samples_do_not_imply_staleness() -> None:
    samples = (
        DeviceSnapshot("x", 0, 20.0, True),
        DeviceSnapshot("x", 1, 20.0, True),
    )
    assert analyze_recording(samples) == ()


@pytest.mark.parametrize("threshold", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_jump_threshold_rejected(threshold: float) -> None:
    with pytest.raises(ValueError, match="jump_threshold"):
        analyze_recording((), jump_threshold_c=threshold)
