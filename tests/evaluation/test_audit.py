"""Audit chains detect edits and record reordering without network access."""

from dataclasses import replace

import pytest

from ares.evaluation.audit import (
    AuditIntegrityError,
    append_entry,
    from_jsonl,
    to_jsonl,
    verify_entries,
)


def test_roundtrip_and_deterministic_hash() -> None:
    entries = append_entry((), "diagnostic", {"severity": "critical"})
    entries = append_entry(entries, "consistency", {"findings": []})
    assert from_jsonl(to_jsonl(entries)) == entries
    assert entries[0].digest == append_entry((), "diagnostic", {"severity": "critical"})[0].digest


def test_tampered_payload_rejected() -> None:
    entries = append_entry((), "diagnostic", {"severity": "normal"})
    tampered = (replace(entries[0], payload={"severity": "critical"}),)
    with pytest.raises(AuditIntegrityError):
        verify_entries(tampered)


def test_reordering_and_missing_middle_rejected() -> None:
    entries = append_entry((), "one", {})
    entries = append_entry(entries, "two", {})
    entries = append_entry(entries, "three", {})
    with pytest.raises(AuditIntegrityError):
        verify_entries((entries[1], entries[0], entries[2]))
    with pytest.raises(AuditIntegrityError):
        verify_entries((entries[0], entries[2]))


def test_invalid_json_and_unexpected_fields_rejected() -> None:
    for content in ('{invalid}', '{"other": 1}', '[]', "\n"):
        with pytest.raises(AuditIntegrityError):
            from_jsonl(content)


def test_non_serializable_payload_rejected() -> None:
    with pytest.raises(TypeError):
        append_entry((), "event", {"bad": object()})


def test_empty_chain_is_valid() -> None:
    assert to_jsonl(()) == ""
    assert from_jsonl("") == ()


def test_non_finite_payload_rejected() -> None:
    with pytest.raises(ValueError):
        append_entry((), "event", {"bad": float("nan")})
