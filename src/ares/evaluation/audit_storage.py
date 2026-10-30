"""Explicit local JSONL audit persistence with validation and atomic replacement.

Intended for a single trusted local operator, not a multi-user audit service.
"""

import os
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from ares.evaluation.audit import AuditEntry, AuditIntegrityError, from_jsonl, to_jsonl


def read_audit(path: Path) -> tuple[AuditEntry, ...]:
    """Reject malformed stored chains; missing file means no prior events."""
    if path.is_symlink():
        raise AuditIntegrityError("audit_symlink_forbidden")
    if not path.exists():
        return ()
    return from_jsonl(path.read_text(encoding="utf-8"))


def save_audit(path: Path, entries: tuple[AuditEntry, ...]) -> None:
    """Atomically replace complete verified chain at an explicitly chosen path.

    This does NOT prevent concurrent writers, tail truncation, rollback,
    replacement of the whole chain, or writes through untrusted symlinks.
    """
    if path.is_symlink():
        raise AuditIntegrityError("audit_symlink_forbidden")
    content = to_jsonl(entries)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".ares-audit-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def _exclusive_writer(path: Path) -> Generator[None]:
    """Acquire a cooperative cross-process lock without waiting or stale-lock eviction."""
    lock = path.with_name(path.name + ".lock")
    if lock.is_symlink():
        raise AuditIntegrityError("audit_lock_invalid")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise AuditIntegrityError("audit_writer_busy") from exc
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def extend_audit(
    path: Path, current: tuple[AuditEntry, ...], next_entries: tuple[AuditEntry, ...]
) -> None:
    """Refuse stale callers and invalid replacements before saving."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_writer(path):
        stored = read_audit(path)
        if stored != current:
            raise AuditIntegrityError("audit_concurrent_or_stale")
        if len(next_entries) != len(current) + 1 or next_entries[:-1] != current:
            raise AuditIntegrityError("audit_invalid_extension")
        save_audit(path, next_entries)
