"""Validated, strictly read-only recorded temperature observations."""

import json
from math import isfinite
from pathlib import Path
from typing import cast

from ares.integrations.replay_timing import TimedReading, analyze_timing
from ares.simulation import DeviceSnapshot


class RecordingError(ValueError):
    """A recorded telemetry file is malformed or unsafe to replay."""


def _unique_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON keys instead of silently accepting the last value."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RecordingError("recording_duplicate_field")
        result[key] = value
    return result


def _reject_nonfinite_constant(value: str) -> object:
    """Python's JSON decoder otherwise accepts non-standard NaN/Infinity tokens."""
    raise RecordingError("recording_invalid_number")


class RecordedSensor:
    """Replay a finite, immutable list of local sensor observations.

    No network access, device discovery or actuation is provided.
    """

    def __init__(
        self, snapshots: tuple[DeviceSnapshot, ...], *, timestamps_s: tuple[float, ...] = ()
    ) -> None:
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
        if timestamps_s:
            if len(timestamps_s) != len(snapshots):
                raise RecordingError("recording_invalid_timestamps")
            try:
                analyze_timing(
                    tuple(TimedReading(index, timestamp) for index, timestamp in enumerate(timestamps_s)),
                    max_gap_s=1.0,
                )
            except ValueError as exc:
                raise RecordingError("recording_invalid_timestamps") from exc
        self.timestamps_s = timestamps_s
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
            value: object = json.loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=_unique_fields,
                parse_constant=_reject_nonfinite_constant,
            )
        except RecordingError:
            raise
        except (UnicodeError, ValueError) as exc:
            raise RecordingError("recording_invalid_json") from exc
        if not isinstance(value, list):
            raise RecordingError("recording_invalid_shape")
        items = cast("list[object]", value)
        if not 1 <= len(items) <= 10000:
            raise RecordingError("recording_invalid_count")
        snapshots: list[DeviceSnapshot] = []
        timestamps: list[float] = []
        timestamped: bool | None = None
        for item in items:
            if not isinstance(item, dict):
                raise RecordingError("recording_invalid_entry")
            fields = cast("dict[str, object]", item)
            keys = set(fields)
            has_timestamp = "timestamp_s" in keys
            if keys not in (
                {"device_id", "step", "temperature_c", "healthy"},
                {"device_id", "step", "temperature_c", "healthy", "timestamp_s"},
            ):
                raise RecordingError("recording_invalid_fields")
            if timestamped is None:
                timestamped = has_timestamp
            elif timestamped != has_timestamp:
                raise RecordingError("recording_inconsistent_timestamps")
            if has_timestamp:
                stamp = fields["timestamp_s"]
                if type(stamp) not in (int, float):
                    raise RecordingError("recording_invalid_timestamps")
                timestamps.append(float(cast("int | float", stamp)))
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
            snapshots.append(
                DeviceSnapshot(
                    device_id,
                    step,
                    float(cast("int | float", temperature)),
                    healthy,
                )
            )
        return cls(tuple(snapshots), timestamps_s=tuple(timestamps))
