"""Risk and trend are independent; no LLM can downgrade an incident."""

import pytest

from ares.runtime.evidence_risk import ReviewAction, RiskSeverity, reconcile
from ares.runtime.temporal_evidence import EvidenceReading, EvidenceState


@pytest.mark.parametrize(
    ("values", "severity", "trend", "action"),
    [
        ([20.0], RiskSeverity.NORMAL, EvidenceState.INSUFFICIENT_HISTORY,
         ReviewAction.COLLECT_EVIDENCE),
        ([85.0], RiskSeverity.CRITICAL, EvidenceState.INSUFFICIENT_HISTORY,
         ReviewAction.HUMAN_REVIEW),
        ([20.0, 24.0, 29.0], RiskSeverity.NORMAL, EvidenceState.RISING_TEMPERATURE,
         ReviewAction.INSPECT),
        ([60.0, 60.0, 60.0], RiskSeverity.WARNING, EvidenceState.NO_CONFIRMED_RISE,
         ReviewAction.INSPECT),
        ([85.0, 80.0, 75.0], RiskSeverity.CRITICAL, EvidenceState.NO_CONFIRMED_RISE,
         ReviewAction.HUMAN_REVIEW),
        ([50.0, 85.0, 51.0], RiskSeverity.CRITICAL, EvidenceState.NO_CONFIRMED_RISE,
         ReviewAction.HUMAN_REVIEW),
        ([20.0, 20.0, 20.0], RiskSeverity.NORMAL, EvidenceState.NO_CONFIRMED_RISE,
         ReviewAction.MONITOR),
        ([59.9, 59.9, 59.9], RiskSeverity.NORMAL, EvidenceState.NO_CONFIRMED_RISE,
         ReviewAction.MONITOR),
        ([60.0], RiskSeverity.WARNING, EvidenceState.INSUFFICIENT_HISTORY,
         ReviewAction.INSPECT),
        ([80.0], RiskSeverity.CRITICAL, EvidenceState.INSUFFICIENT_HISTORY,
         ReviewAction.HUMAN_REVIEW),
    ],
)
def test_risk_does_not_disappear_when_evidence_is_flat_or_cooling(
    values: list[float], severity: RiskSeverity, trend: EvidenceState, action: ReviewAction
) -> None:
    readings = tuple(EvidenceReading(index, value) for index, value in enumerate(values))
    result = reconcile(readings)
    assert result.severity is severity
    assert result.evidence.state is trend
    assert result.next_action is action
    assert result.device_actions == "disabled"
    assert result.model_authority == "advisory_only"


@pytest.mark.parametrize(
    "invalid",
    [
        (EvidenceReading(0, 20.0), EvidenceReading(1, float("nan"))),
        (EvidenceReading(0, 85.0), EvidenceReading(1, 25.0, healthy=False)),
        (EvidenceReading(0, float("inf")),),
    ],
)
def test_invalid_telemetry_never_gets_ignored(
    invalid: tuple[EvidenceReading, ...]
) -> None:
    report = reconcile(invalid)
    assert report.severity is RiskSeverity.CRITICAL
    assert report.next_action is ReviewAction.VALIDATE_SENSOR
    assert report.risk_reason == "invalid_telemetry"


@pytest.mark.parametrize(
    ("warning", "critical"),
    [(float("nan"), 80.0), (60.0, float("inf")), (90.0, 80.0), (80.0, 80.0)],
)
def test_unusable_thresholds_rejected(warning: float, critical: float) -> None:
    with pytest.raises(ValueError):
        reconcile((EvidenceReading(0, 20.0),), warning_c=warning, critical_c=critical)


def test_custom_thresholds_and_rise_threshold_are_independent() -> None:
    entries = (
        EvidenceReading(0, 30.0),
        EvidenceReading(1, 33.0),
        EvidenceReading(2, 37.0),
    )
    report = reconcile(entries, warning_c=35, critical_c=50, rise_threshold_c=10)
    assert report.severity is RiskSeverity.WARNING
    assert report.evidence.state is EvidenceState.NO_CONFIRMED_RISE
    assert report.next_action is ReviewAction.INSPECT
