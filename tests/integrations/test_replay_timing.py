"""Offline timestamp evidence tests; no live clock or hardware involved."""

import pytest

from ares.integrations.replay_timing import TimedReading, analyze_timing


def test_recorded_sampling_gap() -> None:
    readings = (
        TimedReading(0, 1.0),
        TimedReading(1, 1.2),
        TimedReading(2, 4.0),
    )
    assert [(f.step, f.code) for f in analyze_timing(readings, max_gap_s=1.0)] == [
        (2, "recorded_sampling_gap")
    ]


def test_no_timestamps_makes_no_staleness_claim() -> None:
    assert analyze_timing((), max_gap_s=1.0) == ()


@pytest.mark.parametrize("max_gap", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_gap_configuration(max_gap: float) -> None:
    with pytest.raises(ValueError, match="max_gap"):
        analyze_timing((), max_gap_s=max_gap)


@pytest.mark.parametrize(
    "readings",
    [
        (TimedReading(0, 1.0), TimedReading(1, 1.0)),
        (TimedReading(0, 2.0), TimedReading(1, 1.0)),
        (TimedReading(0, float("nan")),),
        (TimedReading(1, 1.0),),
    ],
)
def test_invalid_timing_evidence_rejected(readings: tuple[TimedReading, ...]) -> None:
    with pytest.raises(ValueError):
        analyze_timing(readings, max_gap_s=1.0)
