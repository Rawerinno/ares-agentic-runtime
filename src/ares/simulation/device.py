"""A minimal read-only-friendly device simulator for repeatable tests.

A simulated value is *not* a hardware actuator and makes no network calls.
"""

from dataclasses import dataclass


class SimulatedFault(RuntimeError):
    """A simulated sensor read failure."""


@dataclass(frozen=True, slots=True)
class DeviceSnapshot:
    """Timestamp-free deterministic state observed at one simulation step."""

    device_id: str
    step: int
    temperature_c: float
    healthy: bool


class DeviceSimulator:
    """In-memory temperature sensor with configurable deterministic faults."""

    def __init__(
        self,
        device_id: str,
        *,
        initial_temperature_c: float = 20.0,
        increment_c: float = 0.5,
        fault_at_step: int | None = None,
    ) -> None:
        if not device_id.strip():
            raise ValueError("device_id must not be blank")
        if fault_at_step is not None and fault_at_step < 0:
            raise ValueError("fault_at_step must be nonnegative")
        self._device_id = device_id
        self._temperature_c = initial_temperature_c
        self._increment_c = increment_c
        self._fault_at_step = fault_at_step
        self._step = 0

    def read(self) -> DeviceSnapshot:
        """Return current simulated reading without advancing simulation time."""
        if self._fault_at_step is not None and self._step >= self._fault_at_step:
            raise SimulatedFault(f"Sensor fault at step {self._step}")
        return DeviceSnapshot(
            device_id=self._device_id,
            step=self._step,
            temperature_c=self._temperature_c,
            healthy=True,
        )

    def advance(self) -> None:
        """Advance exactly one deterministic simulation tick."""
        self._step += 1
        self._temperature_c += self._increment_c
