"""Audit projection records decisions without model narratives."""

from ares.evaluation.audit import from_jsonl, to_jsonl
from ares.evaluation.diagnostic_audit import record_diagnostic
from ares.intelligence.consistency import check_consistency
from ares.intelligence.decisions import Decision, DecisionKind
from ares.intelligence.diagnostics import build_diagnostic_report
from ares.intelligence.hypotheses import suggested_checks
from ares.intelligence.resilience import OutcomeStatus, ProposalOutcome
from ares.simulation import DeviceSnapshot
from ares.supervisor import Assessment, Severity


def test_audit_records_structured_governed_result_without_narrative() -> None:
    assessment = Assessment(
        DeviceSnapshot("sensor", 1, 20.0, True),
        Severity.NORMAL,
        "Temperature is within limits",
        "Continue observation",
    )
    decision = Decision(DecisionKind.REQUEST_REVIEW, "Private model rationale", Severity.NORMAL)
    outcome = ProposalOutcome(OutcomeStatus.ACCEPTED, decision, None, 10.0)
    report = build_diagnostic_report(assessment, decision)
    checks = check_consistency(assessment, report, suggested_checks(assessment))
    entries = record_diagnostic((), assessment, report, outcome, checks)
    assert len(entries) == 1
    assert entries[0].payload["governed_recommendation"] == "observe"
    assert entries[0].payload["model_recommendation"] == "request_review"
    assert entries[0].payload["consistency_findings"] == ["model_disagreement"]
    assert "Private model rationale" not in to_jsonl(entries)
    assert from_jsonl(to_jsonl(entries)) == entries
