"""Offline replay of validated, recorded telemetry."""

import json
from pathlib import Path

import pytest

from ares.integrations import ReadOnlyToolGateway
from ares.integrations.recorded import RecordedSensor, RecordingError
from ares.safety import Capability, Policy
from ares.supervisor import Severity, Supervisor


def save(tmp_path: Path, events: object) -> Path:
    path = tmp_path / "recording.json"
    path.write_text(json.dumps(events), encoding="utf-8")
    return path


def sample() -> list[dict[str, object]]:
    return [
        {"device_id": "recorded-1", "step": 0, "temperature_c": 22.5, "healthy": True},
        {"device_id": "recorded-1", "step": 1, "temperature_c": 83.0, "healthy": False},
    ]


def test_recorded_sensor_replays_without_advancing_on_read(tmp_path: Path) -> None:
    sensor = RecordedSensor.from_file(save(tmp_path, sample()))
    assert sensor.read().temperature_c == 22.5
    assert sensor.read().step == 0
    sensor.advance()
    assert sensor.read().step == 1
    assert sensor.read().healthy is False
    with pytest.raises(RecordingError, match="exhausted"):
        sensor.advance()


@pytest.mark.parametrize(
    "events",
    [
        [],
        {},
        [{"device_id": "x", "step": 0, "temperature_c": 2.0}],
        [{"device_id": "x", "step": True, "temperature_c": 2.0, "healthy": True}],
        [{"device_id": "x", "step": 0, "temperature_c": True, "healthy": True}],
        [{"device_id": "x", "step": 0, "temperature_c": float("nan"), "healthy": True}],
        [
            {"device_id": "x", "step": 0, "temperature_c": 20, "healthy": True},
            {"device_id": "y", "step": 1, "temperature_c": 21, "healthy": True},
        ],
        [
            {"device_id": "x", "step": 0, "temperature_c": 20, "healthy": True},
            {"device_id": "x", "step": 3, "temperature_c": 21, "healthy": True},
        ],
    ],
)
def test_recording_rejects_invalid_payload(tmp_path: Path, events: object) -> None:
    with pytest.raises(RecordingError):
        RecordedSensor.from_file(save(tmp_path, events))


def test_recording_rejects_large_file(tmp_path: Path) -> None:
    path = tmp_path / "recording.json"
    path.write_bytes(b" " * (1024 * 1024 + 1))
    with pytest.raises(RecordingError, match="large"):
        RecordedSensor.from_file(path)


def test_recording_rejects_symlink(tmp_path: Path) -> None:
    target = save(tmp_path, sample())
    link = tmp_path / "linked.json"
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError):
        pytest.skip("Symlink unavailable")
    with pytest.raises(RecordingError, match="symlink"):
        RecordedSensor.from_file(link)


def test_recorded_sensor_passes_through_authorized_gateway(tmp_path: Path) -> None:
    sensor = RecordedSensor.from_file(save(tmp_path, sample()))
    gateway = ReadOnlyToolGateway(Policy(frozenset({("supervisor", "recorded", Capability.READ)})))
    gateway.register_sensor("recorded", sensor)
    supervisor = Supervisor(gateway)
    assert supervisor.assess(agent_id="supervisor", tool_id="recorded").severity is Severity.NORMAL
    sensor.advance()
    second = supervisor.assess(agent_id="supervisor", tool_id="recorded")
    assert second.severity is Severity.CRITICAL
