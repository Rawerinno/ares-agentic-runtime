"""Deterministic anomaly indicators for recorded data, not live sensor alarms."""

from dataclasses import dataclass
from math import isfinite

from ares.simulation import DeviceSnapshot


@dataclass(frozen=True, slots=True)
class ReplayFinding:
    step: int
    code: str


def analyze_recording(
    snapshots: tuple[DeviceSnapshot, ...], *, jump_threshold_c: float = 20.0
) -> tuple[ReplayFinding, ...]:
    """Flag abrupt steps and unhealthy samples without inventing timestamps.

    Consecutive identical readings are not proof of staleness: recordings have
    no timestamps or guaranteed sample rate.
    """
    if not isfinite(jump_threshold_c) or jump_threshold_c <= 0:
        raise ValueError("jump_threshold_c must be finite and positive")
    findings: list[ReplayFinding] = []
    previous: DeviceSnapshot | None = None
    for snapshot in snapshots:
        if not snapshot.healthy:
            findings.append(ReplayFinding(snapshot.step, "sensor_unhealthy"))
        if previous is not None and abs(snapshot.temperature_c - previous.temperature_c) >= jump_threshold_c:
            findings.append(ReplayFinding(snapshot.step, "temperature_jump"))
        previous = snapshot
    return tuple(findings)
