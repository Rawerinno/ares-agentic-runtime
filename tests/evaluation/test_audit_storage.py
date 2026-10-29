"""Opt-in local audit storage keeps and verifies a chain."""

from pathlib import Path

import pytest

from ares.evaluation.audit import AuditIntegrityError, append_entry
from ares.evaluation.audit_storage import extend_audit, read_audit
from ares.intelligence.ollama_demo import run


def test_extend_across_sessions(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    assert read_audit(path) == ()
    first = append_entry((), "one", {"severity": "normal"})
    extend_audit(path, (), first)
    second = append_entry(read_audit(path), "two", {"severity": "critical"})
    extend_audit(path, first, second)
    assert read_audit(path) == second


def test_stale_writer_and_tampering_rejected(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    first = append_entry((), "one", {})
    extend_audit(path, (), first)
    with pytest.raises(AuditIntegrityError):
        extend_audit(path, (), append_entry((), "two", {}))
    path.write_text(path.read_text().replace('"one"', '"bad"'), encoding="utf-8")
    with pytest.raises(AuditIntegrityError):
        read_audit(path)


def test_demo_persists_only_when_requested(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    assert run(["--temperature", "85", "--audit-file", str(path)]) == 0
    assert run(["--temperature", "20", "--audit-file", str(path)]) == 0
    assert len(read_audit(path)) == 2
    assert run(["--temperature", "20"]) == 0
    assert len(read_audit(path)) == 2
