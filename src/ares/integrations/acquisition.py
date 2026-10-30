"""A transport-neutral, strictly read-only acquisition boundary.

The caller owns the transport timeout. This module never opens ports, sockets,
or devices and never issues commands to hardware.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from typing import cast

from ares.integrations.recorded import RecordingError, reject_nonfinite_json_constant, unique_json_fields
from ares.simulation import DeviceSnapshot


@dataclass(frozen=True, slots=True)
class AcquisitionResult:
    snapshot: DeviceSnapshot | None
    error_code: str | None


class BoundedAcquisition:
    """Validate one bounded response from an injected read-only transport."""

    def __init__(self, receive: Callable[[float], bytes], *, timeout_s: float = 1.0) -> None:
        if not isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError("timeout_s must be finite and positive")
        self._receive = receive
        self._timeout_s = timeout_s
        self._next_step = 0
        self._device_id: str | None = None

    def read(self) -> AcquisitionResult:
        """Read one frame; fail closed on timeout, transport or schema errors."""
        try:
            frame = self._receive(self._timeout_s)
        except TimeoutError:
            return AcquisitionResult(None, "acquisition_timeout")
        except (OSError, ConnectionError):
            return AcquisitionResult(None, "acquisition_transport_error")
        if type(frame) is not bytes or not 0 < len(frame) <= 4096:
            return AcquisitionResult(None, "acquisition_invalid_frame")
        try:
            value: object = json.loads(
                frame.decode("utf-8"),
                object_pairs_hook=unique_json_fields,
                parse_constant=reject_nonfinite_json_constant,
            )
        except (UnicodeError, ValueError, RecordingError):
            return AcquisitionResult(None, "acquisition_invalid_json")
        if not isinstance(value, dict):
            return AcquisitionResult(None, "acquisition_invalid_schema")
        fields = cast("dict[str, object]", value)
        if set(fields) != {"device_id", "step", "temperature_c", "healthy"}:
            return AcquisitionResult(None, "acquisition_invalid_schema")
        device_id = fields["device_id"]
        step = fields["step"]
        temperature = fields["temperature_c"]
        healthy = fields["healthy"]
        if (
            type(device_id) is not str
            or not device_id.strip()
            or type(step) is not int
            or type(temperature) not in (int, float)
            or type(healthy) is not bool
        ):
            return AcquisitionResult(None, "acquisition_invalid_schema")
        value_c = float(cast("int | float", temperature))
        if not isfinite(value_c):
            return AcquisitionResult(None, "acquisition_invalid_schema")
        if step != self._next_step or (
            self._device_id is not None and device_id != self._device_id
        ):
            return AcquisitionResult(None, "acquisition_invalid_sequence")
        self._device_id = device_id
        self._next_step += 1
        return AcquisitionResult(DeviceSnapshot(device_id, step, value_c, healthy), None)
