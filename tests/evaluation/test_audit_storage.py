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


def test_truncated_or_modified_history_rejected(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    first = append_entry((), "one", {"severity": "normal"})
    second = append_entry(first, "two", {"severity": "critical"})
    extend_audit(path, (), first)
    extend_audit(path, first, second)
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines()
    path.write_text(lines[1] + "\n", encoding="utf-8")
    with pytest.raises(AuditIntegrityError):
        read_audit(path)
    path.write_text(original.replace('"critical"', '"normal"'), encoding="utf-8")
    with pytest.raises(AuditIntegrityError):
        read_audit(path)


def test_selected_symlink_path_rejected(tmp_path: Path) -> None:
    path = tmp_path / "target.jsonl"
    link = tmp_path / "link.jsonl"
    path.write_text("", encoding="utf-8")
    try:
        link.symlink_to(path)
    except (OSError, NotImplementedError):
        pytest.skip("Symbolic links not available on this system")
    with pytest.raises(AuditIntegrityError, match="symlink"):
        read_audit(link)
    with pytest.raises(AuditIntegrityError, match="symlink"):
        extend_audit(link, (), append_entry((), "event", {}))


def test_existing_writer_lock_rejects_append(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    lock = tmp_path / "audit.jsonl.lock"
    lock.write_text("held", encoding="utf-8")
    with pytest.raises(AuditIntegrityError, match="audit_writer_busy"):
        extend_audit(path, (), append_entry((), "event", {}))
    assert lock.read_text(encoding="utf-8") == "held"
    assert not path.exists()


def test_lock_released_after_rejected_stale_append(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    first = append_entry((), "first", {})
    extend_audit(path, (), first)
    with pytest.raises(AuditIntegrityError, match="stale"):
        extend_audit(path, (), append_entry((), "second", {}))
    assert not path.with_name(path.name + ".lock").exists()
    second = append_entry(first, "second", {})
    extend_audit(path, first, second)
    assert read_audit(path) == second


def test_atomic_replace_failure_preserves_previous_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ares.evaluation import audit_storage

    path = tmp_path / "audit.jsonl"
    first = append_entry((), "initial", {"value": 1})
    extend_audit(path, (), first)
    before = path.read_bytes()

    def broken_replace(source: str, destination: Path) -> None:
        raise OSError("simulated storage failure")

    monkeypatch.setattr(audit_storage.os, "replace", broken_replace)
    with pytest.raises(OSError, match="simulated storage failure"):
        extend_audit(path, first, append_entry(first, "next", {"value": 2}))

    assert path.read_bytes() == before
    assert read_audit(path) == first
    assert not path.with_name(path.name + ".lock").exists()
    assert list(tmp_path.glob(".ares-audit-*")) == []
