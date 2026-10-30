"""Validated, strictly read-only recorded temperature observations."""

import json
from math import isfinite
from pathlib import Path
from typing import cast

from ares.simulation import DeviceSnapshot


class RecordingError(ValueError):
    """A recorded telemetry file is malformed or unsafe to replay."""


class RecordedSensor:
    """Replay a finite, immutable list of local sensor observations.

    No network access, device discovery or actuation is provided.
    """

    def __init__(self, snapshots: tuple[DeviceSnapshot, ...]) -> None:
        if not snapshots:
            raise RecordingError("recording_empty")
        if len(snapshots) > 10000:
            raise RecordingError("recording_too_long")
        device_id = snapshots[0].device_id
        for index, snapshot in enumerate(snapshots):
            if (
                not device_id.strip()
                or snapshot.device_id != device_id
                or snapshot.step != index
                or not isfinite(snapshot.temperature_c)
            ):
                raise RecordingError("recording_invalid_sequence")
        self._snapshots = snapshots
        self._offset = 0

    def read(self) -> DeviceSnapshot:
        """Return the current event; never advance on an observation."""
        return self._snapshots[self._offset]

    def advance(self) -> None:
        """Replay only within the existing recording."""
        if self._offset + 1 >= len(self._snapshots):
            raise RecordingError("recording_exhausted")
        self._offset += 1

    @classmethod
    def from_file(cls, path: Path) -> "RecordedSensor":
        """Load a bounded local JSON file with an exact schema."""
        if path.is_symlink():
            raise RecordingError("recording_symlink_forbidden")
        if path.stat().st_size > 1024 * 1024:
            raise RecordingError("recording_file_too_large")
        try:
            value: object = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise RecordingError("recording_invalid_json") from exc
        if not isinstance(value, list):
            raise RecordingError("recording_invalid_shape")
        items = cast("list[object]", value)
        if not 1 <= len(items) <= 10000:
            raise RecordingError("recording_invalid_count")
        snapshots: list[DeviceSnapshot] = []
        for item in items:
            if not isinstance(item, dict):
                raise RecordingError("recording_invalid_entry")
            fields = cast("dict[str, object]", item)
            if set(fields) != {"device_id", "step", "temperature_c", "healthy"}:
                raise RecordingError("recording_invalid_fields")
            device_id = fields["device_id"]
            step = fields["step"]
            temperature = fields["temperature_c"]
            healthy = fields["healthy"]
            if (
                type(device_id) is not str
                or type(step) is not int
                or type(temperature) not in (int, float)
                or type(healthy) is not bool
            ):
                raise RecordingError("recording_invalid_types")
            snapshots.append(DeviceSnapshot(device_id, step, float(temperature), healthy))
        return cls(tuple(snapshots))
