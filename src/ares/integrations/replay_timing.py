"""Timestamp-based replay checks; never infer clock evidence from sample indices."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class TimedReading:
    step: int
    timestamp_s: float


@dataclass(frozen=True, slots=True)
class TemporalFinding:
    step: int
    code: str


def analyze_timing(
    readings: tuple[TimedReading, ...], *, max_gap_s: float
) -> tuple[TemporalFinding, ...]:
    """Report recorded gaps only when timestamps are explicit and strictly increasing.

    This is offline evidence, not a live sensor timeout. It cannot infer whether
    the current device is stale because no current wall-clock observation exists.
    """
    if not isfinite(max_gap_s) or max_gap_s <= 0:
        raise ValueError("max_gap_s must be finite and positive")
    findings: list[TemporalFinding] = []
    previous: TimedReading | None = None
    for expected, reading in enumerate(readings):
        if type(reading.step) is not int or reading.step != expected:
            raise ValueError("invalid_timing_step")
        if not isfinite(reading.timestamp_s):
            raise ValueError("invalid_timing_timestamp")
        if previous is not None:
            delta = reading.timestamp_s - previous.timestamp_s
            if delta <= 0:
                raise ValueError("nonmonotonic_timestamps")
            if delta > max_gap_s:
                findings.append(TemporalFinding(reading.step, "recorded_sampling_gap"))
        previous = reading
    return tuple(findings)
