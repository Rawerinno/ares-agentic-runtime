"""Offline read-only audit console can verify complete persisted task history."""

import json
from pathlib import Path

import pytest
from pytest import CaptureFixture

from ares.runtime.evidence_team import evidence_team_reference_generate
from ares.runtime.evidence_team_audit_console import run, summarize
from ares.runtime.evidence_team_store import DurableEvidenceStore, run_durable_evidence_team
from ares.runtime.temporal_evidence import EvidenceReading


def test_complete_audit_verifies_reports_without_model_calls(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "audit.sqlite"
    store = DurableEvidenceStore(db_path)
    for index, temperature in enumerate((20.0, 65.0, 85.0)):
        run_durable_evidence_team(
            store,
            evidence_team_reference_generate,
            (EvidenceReading(0, temperature),),
            task_id=f"case-{index}",
            identity="reference-v1",
        )
    summary = summarize(db_path)
    assert summary["status_counts"] == {"completed": 3}
    assert summary["completed_verified"] == 3
    assert summary["critical_incidents"] == 1
    assert summary["complete_coverage"]
    assert summary["device_actions"] == "disabled"
    assert run(["--db", str(db_path)]) == 0
    assert json.loads(capsys.readouterr().out) == summary


def test_truncation_is_explicit_and_exit_nonzero(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.sqlite"
    store = DurableEvidenceStore(db_path)
    for index in range(3):
        run_durable_evidence_team(
            store,
            evidence_team_reference_generate,
            (EvidenceReading(0, 20.0),),
            task_id=f"case-{index}",
            identity="reference-v1",
        )
    report = summarize(db_path, limit=2)
    assert report["completed_verified"] == 2
    assert report["truncated"]
    assert not report["complete_coverage"]
    assert run(["--db", str(db_path), "--limit", "2"]) == 1


def test_incomplete_tasks_are_visible_without_recovery(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.sqlite"
    store = DurableEvidenceStore(db_path)
    assert store.claim("unfinished", "hash") is None
    summary = summarize(db_path)
    assert summary["status_counts"] == {"running": 1}
    assert summary["unresolved_tasks"] == 1
    assert run(["--db", str(db_path)]) == 1


def test_missing_database_is_not_created(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    db_path = tmp_path / "not-created.sqlite"
    assert run(["--db", str(db_path)]) == 2
    assert not db_path.exists()
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "ValueError"


def test_existing_corrupt_record_is_rejected(tmp_path: Path) -> None:
    import sqlite3

    db_path = tmp_path / "audit.sqlite"
    store = DurableEvidenceStore(db_path)
    run_durable_evidence_team(
        store,
        evidence_team_reference_generate,
        (EvidenceReading(0, 85.0),),
        task_id="case",
        identity="reference-v1",
    )
    with sqlite3.connect(db_path) as db:
        db.execute("UPDATE evidence_tasks SET digest = 'corrupted'")
    with pytest.raises(ValueError, match="checksum"):
        summarize(db_path)
    assert run(["--db", str(db_path)]) == 2


def test_unknown_status_is_rejected(tmp_path: Path) -> None:
    import sqlite3

    db_path = tmp_path / "audit.sqlite"
    store = DurableEvidenceStore(db_path)
    store.claim("untrusted", "hash")
    with sqlite3.connect(db_path) as db:
        db.execute("UPDATE evidence_tasks SET status = 'authorized_to_act'")
    with pytest.raises(ValueError, match="invalid status"):
        summarize(db_path)


@pytest.mark.parametrize("limit", [0, 1001])
def test_invalid_limits_are_rejected(tmp_path: Path, limit: int) -> None:
    path = tmp_path / "audit.sqlite"
    DurableEvidenceStore(path)
    with pytest.raises(ValueError):
        summarize(path, limit=limit)
