"""Deterministic reference adapter for the proposal-only intelligence boundary."""

from ares.supervisor import Assessment, Severity


class LocalReferenceModel:
    """Offline baseline with the same output schema as future model providers."""

    def propose(self, assessment: Assessment) -> object:
        if assessment.severity is Severity.CRITICAL:
            kind = "request_review"
            rationale = "Critical assessment requires an engineer review"
        elif assessment.severity is Severity.WARNING:
            kind = "investigate"
            rationale = "Investigate warning telemetry before any intervention"
        else:
            kind = "observe"
            rationale = "Continue monitoring normal telemetry"
        return {
            "kind": kind,
            "rationale": rationale,
            "assessment_severity": assessment.severity.value,
        }
