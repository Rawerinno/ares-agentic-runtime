"""Audit CLI validates, and reports tampering without leaking details."""

from pathlib import Path

from _pytest.capture import CaptureFixture

from ares.evaluation.audit import append_entry
from ares.evaluation.audit_storage import save_audit
from ares.evaluation.audit_verify import run


def test_valid_chain(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    path = tmp_path / "records.jsonl"
    save_audit(path, append_entry((), "diagnostic", {"severity": "critical"}))
    assert run([str(path)]) == 0
    assert '"valid": true' in capsys.readouterr().out


def test_missing_and_corrupted_chain(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    path = tmp_path / "records.jsonl"
    assert run([str(path)]) == 1
    assert "audit_file_missing" in capsys.readouterr().out
    path.write_text("not-json", encoding="utf-8")
    assert run([str(path)]) == 1
    assert "audit_invalid" in capsys.readouterr().out
