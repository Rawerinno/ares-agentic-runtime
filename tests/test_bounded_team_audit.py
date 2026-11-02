"""Offline audit integration tests for the bounded ARES team."""

from pathlib import Path

import pytest

from ares.evaluation.audit import from_jsonl, to_jsonl
from ares.evaluation.audit_storage import extend_audit, read_audit
from ares.evaluation.bounded_team import BoundedTeamResult
from ares.evaluation.bounded_team_audit import record_bounded_execution
from ares.evaluation.concurrency_policy import SchedulingDecision


def scheduler() -> SchedulingDecision:
    return SchedulingDecision(1, False, "insufficient_evidence", 0, 3, None, None)


def test_audit_records_no_measurements_or_model_text(tmp_path: Path) -> None:
    result = BoundedTeamResult(
        "verified", ("secret-reading", "60", "65"), "60", "60", "warning", ()
    )
    entries = record_bounded_execution((), result, scheduler(), call_count=4, elapsed_ms=2500)
    path = tmp_path / "audit.jsonl"
    extend_audit(path, (), entries)
    loaded = read_audit(path)
    assert loaded == entries
    assert loaded[0].event == "bounded_team_completed"
    assert loaded[0].payload["severity"] == "warning"
    stored = path.read_text(encoding="utf-8")
    assert "secret-reading" not in stored
    assert "advisory_only" in stored


def test_rejected_results_have_no_severity_and_chain_remains_valid() -> None:
    first = record_bounded_execution(
        (),
        BoundedTeamResult("verified", ("55",), "60", "60", "warning", ()),
        scheduler(),
        call_count=2,
        elapsed_ms=800,
    )
    second = record_bounded_execution(
        first,
        BoundedTeamResult("rejected", ("bad",), None, None, None, ("extractor_mismatch",)),
        scheduler(),
        call_count=1,
        elapsed_ms=500,
    )
    assert second[-1].sequence == 2
    assert second[-1].previous_hash == first[-1].digest
    assert second[-1].payload["severity"] is None
    assert from_jsonl(to_jsonl(second)) == second


def test_invalid_metrics_rejected() -> None:
    result = BoundedTeamResult("rejected", (), None, None, None, ())
    with pytest.raises(ValueError):
        record_bounded_execution((), result, scheduler(), call_count=-1, elapsed_ms=0)
    with pytest.raises(ValueError):
        record_bounded_execution((), result, scheduler(), call_count=0, elapsed_ms=-0.1)


def test_rejected_result_cannot_carry_a_severity() -> None:
    invalid = BoundedTeamResult("rejected", (), None, None, "critical", ("error",))
    with pytest.raises(ValueError):
        record_bounded_execution((), invalid, scheduler(), call_count=1, elapsed_ms=1)
