"""Adversarial JSONL audit parsing regression tests."""

import json

import pytest

from ares.evaluation.audit import AuditIntegrityError, append_entry, from_jsonl, to_jsonl


def test_valid_audit_jsonl_roundtrip() -> None:
    entries = append_entry((), "diagnostic", {"temperature": 60})
    assert from_jsonl(to_jsonl(entries)) == entries


@pytest.mark.parametrize(
    "mutate",
    [
        lambda line: line.replace('"event": "diagnostic"', '"event": "diagnostic", "event": "diagnostic"'),
        lambda line: line.replace('"temperature": 60', '"temperature": 60, "temperature": 60'),
    ],
)
def test_duplicate_json_keys_fail_closed(mutate) -> None:
    entries = append_entry((), "diagnostic", {"temperature": 60})
    original = json.loads(to_jsonl(entries))
    line = json.dumps(original, sort_keys=True)
    with pytest.raises(AuditIntegrityError):
        from_jsonl(mutate(line) + "\n")
