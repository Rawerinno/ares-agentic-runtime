"""Deterministic reconciliation of risk, evidence quality and advisory follow-ups.

This module deliberately does NOT infer root cause from temperature.
Severity is based on the worst observed state within a bounded incident
window; a previous critical excursion cannot be cleared by a later
cooling reading without a separate, authorized reset workflow.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from ares.runtime.temporal_evidence import (
    EvidenceReading,
    EvidenceReport,
    EvidenceState,
    analyze_evidence,
)


class RiskSeverity(StrEnum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


class ReviewAction(StrEnum):
    MONITOR = "monitor"
    COLLECT_EVIDENCE = "collect_evidence"
    INSPECT = "inspect"
    VALIDATE_SENSOR = "validate_sensor"
    HUMAN_REVIEW = "human_review"


@dataclass(frozen=True, slots=True)
class ReconciledTriage:
    severity: RiskSeverity
    evidence: EvidenceReport
    next_action: ReviewAction
    risk_reason: str
    model_authority: str = "advisory_only"
    device_actions: str = "disabled"


def reconcile(
    readings: Sequence[EvidenceReading],
    *,
    warning_c: float = 60.0,
    critical_c: float = 80.0,
    rise_threshold_c: float = 5.0,
) -> ReconciledTriage:
    """Risk is assessed independently of the direction of a temperature trend.

    All observations are local synthetic data; no model input changes
    either severity or the authorized follow-up. On invalid history,
    fail closed rather than silently discard a failed sample.
    """
    if not (isfinite(warning_c) and isfinite(critical_c)):
        raise ValueError("risk thresholds must be finite")
    if warning_c >= critical_c:
        raise ValueError("warning must be below critical")
    evidence = analyze_evidence(readings, rise_threshold_c=rise_threshold_c)
    if evidence.state is EvidenceState.INVALID_TELEMETRY:
        severity = RiskSeverity.CRITICAL
        action = ReviewAction.VALIDATE_SENSOR
        reason = "invalid_telemetry"
    elif evidence.highest_c is not None and evidence.highest_c >= critical_c:
        severity = RiskSeverity.CRITICAL
        action = ReviewAction.HUMAN_REVIEW
        reason = "critical_excursion"
    elif evidence.highest_c is not None and evidence.highest_c >= warning_c:
        severity = RiskSeverity.WARNING
        action = ReviewAction.INSPECT
        reason = "warning_excursion"
    elif evidence.state is EvidenceState.RISING_TEMPERATURE:
        severity = RiskSeverity.NORMAL
        action = ReviewAction.INSPECT
        reason = "rising_below_threshold"
    elif evidence.state is EvidenceState.INSUFFICIENT_HISTORY:
        severity = RiskSeverity.NORMAL
        action = ReviewAction.COLLECT_EVIDENCE
        reason = "insufficient_history"
    else:
        severity = RiskSeverity.NORMAL
        action = ReviewAction.MONITOR
        reason = "no_detected_anomaly"
    return ReconciledTriage(severity, evidence, action, reason)
