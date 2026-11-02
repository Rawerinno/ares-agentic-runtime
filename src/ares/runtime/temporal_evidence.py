"""Evidence-only triage of bounded telemetry histories.

This module does not infer physical root causes from a temperature alone.
A thermal rise is an observation, not proof of thermal load or sensor failure.
"""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from collections.abc import Sequence


class EvidenceState(StrEnum):
    INVALID_TELEMETRY = "invalid_telemetry"
    INSUFFICIENT_HISTORY = "insufficient_history"
    RISING_TEMPERATURE = "rising_temperature"
    NO_CONFIRMED_RISE = "no_confirmed_rise"


@dataclass(frozen=True, slots=True)
class EvidenceReading:
    step: int
    temperature_c: float
    healthy: bool = True


@dataclass(frozen=True, slots=True)
class EvidenceReport:
    state: EvidenceState
    sample_count: int
    valid_count: int
    delta_c: float | None
    highest_c: float | None
    suggested_followup: str
    device_actions: str = "disabled"


_FOLLOWUP = {
    EvidenceState.INVALID_TELEMETRY: "validate_sensor",
    EvidenceState.INSUFFICIENT_HISTORY: "collect_more_samples",
    EvidenceState.RISING_TEMPERATURE: "inspect_thermal_system",
    EvidenceState.NO_CONFIRMED_RISE: "continue_monitoring",
}


def analyze_evidence(
    readings: Sequence[EvidenceReading], *, rise_threshold_c: float = 5.0
) -> EvidenceReport:
    """Classify evidence, not device health, with conservative failure ordering.

    Samples must be ordered by strict monotonically increasing simulation step.
    Any invalid sensor sample invalidates the trace rather than getting ignored.
    At least three valid observations are needed for a trend claim.
    """
    if not 1 <= len(readings) <= 32:
        raise ValueError("expected 1..32 readings")
    if not isfinite(rise_threshold_c) or rise_threshold_c <= 0:
        raise ValueError("rise threshold must be finite and positive")
    previous = -1
    for reading in readings:
        if reading.step < 0 or reading.step <= previous:
            raise ValueError("steps must be strictly increasing and nonnegative")
        previous = reading.step
    valid = [reading for reading in readings if reading.healthy and isfinite(reading.temperature_c)]
    if len(valid) != len(readings):
        state = EvidenceState.INVALID_TELEMETRY
        delta = None
        highest = None
    elif len(valid) < 3:
        state = EvidenceState.INSUFFICIENT_HISTORY
        delta = None
        highest = max(reading.temperature_c for reading in valid)
    else:
        delta = valid[-1].temperature_c - valid[0].temperature_c
        highest = max(reading.temperature_c for reading in valid)
        # A single anomalous point should not establish a persistent rise.
        monotone = all(
            later.temperature_c >= earlier.temperature_c
            for earlier, later in zip(valid, valid[1:], strict=False)
        )
        state = (
            EvidenceState.RISING_TEMPERATURE
            if monotone and delta >= rise_threshold_c
            else EvidenceState.NO_CONFIRMED_RISE
        )
    return EvidenceReport(
        state=state,
        sample_count=len(readings),
        valid_count=len(valid),
        delta_c=delta,
        highest_c=highest,
        suggested_followup=_FOLLOWUP[state],
    )
