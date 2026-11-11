"""Deterministic hash-chained audit entries for diagnostic outcomes.

This module does not persist or transmit data, nor does it provide signatures.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import cast


class AuditIntegrityError(ValueError):
    """The audit sequence is malformed or has an invalid hash chain."""


@dataclass(frozen=True, slots=True)
class AuditEntry:
    sequence: int
    previous_hash: str
    event: str
    payload: dict[str, object]
    digest: str


def _canonical(value: dict[str, object]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def append_entry(
    existing: tuple[AuditEntry, ...], event: str, payload: dict[str, object]
) -> tuple[AuditEntry, ...]:
    """Append only after checking the entire in-memory chain."""
    verify_entries(existing)
    if not event or len(event) > 80 or not event.isascii():
        raise ValueError("Invalid audit event name")
    sequence = len(existing) + 1
    previous_hash = existing[-1].digest if existing else "0" * 64
    body: dict[str, object] = {
        "sequence": sequence,
        "previous_hash": previous_hash,
        "event": event,
        "payload": payload,
    }
    digest = hashlib.sha256(_canonical(body)).hexdigest()
    entry = AuditEntry(sequence, previous_hash, event, payload.copy(), digest)
    return (*existing, entry)


def verify_entries(entries: tuple[AuditEntry, ...]) -> None:
    """Detect modified, removed-middle, or reordered entries in a supplied chain."""
    expected_previous = "0" * 64
    for sequence, entry in enumerate(entries, start=1):
        if entry.sequence != sequence or entry.previous_hash != expected_previous:
            raise AuditIntegrityError("audit_sequence_invalid")
        body: dict[str, object] = {
            "sequence": entry.sequence,
            "previous_hash": entry.previous_hash,
            "event": entry.event,
            "payload": entry.payload,
        }
        try:
            digest = hashlib.sha256(_canonical(body)).hexdigest()
        except (TypeError, ValueError) as exc:
            raise AuditIntegrityError("audit_payload_invalid") from exc
        if entry.digest != digest:
            raise AuditIntegrityError("audit_digest_invalid")
        expected_previous = digest


def to_jsonl(entries: tuple[AuditEntry, ...]) -> str:
    """Serialize a verified chain; caller owns storage and access controls."""
    verify_entries(entries)
    lines = [
        json.dumps(
            {
                "sequence": entry.sequence,
                "previous_hash": entry.previous_hash,
                "event": entry.event,
                "payload": entry.payload,
                "digest": entry.digest,
            },
            sort_keys=True,
            allow_nan=False,
        )
        for entry in entries
    ]
    return "\n".join(lines) + ("\n" if lines else "")


def _unique_object_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject ambiguous JSON objects at every nesting level."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise AuditIntegrityError("audit_duplicate_json_key")
        result[key] = value
    return result


def from_jsonl(content: str) -> tuple[AuditEntry, ...]:
    """Reject malformed or tampered JSONL without partial recovery."""
    entries: list[AuditEntry] = []
    try:
        for line in content.splitlines():
            if not line:
                raise AuditIntegrityError("audit_blank_line")
            value: object = json.loads(line, object_pairs_hook=_unique_object_keys)
            if not isinstance(value, dict):
                raise AuditIntegrityError("audit_record_invalid")
            fields = cast("dict[str, object]", value)
            if set(fields) != {"sequence", "previous_hash", "event", "payload", "digest"}:
                raise AuditIntegrityError("audit_fields_invalid")
            if (
                type(fields["sequence"]) is not int
                or type(fields["previous_hash"]) is not str
                or type(fields["event"]) is not str
                or not isinstance(fields["payload"], dict)
                or type(fields["digest"]) is not str
            ):
                raise AuditIntegrityError("audit_types_invalid")
            entries.append(
                AuditEntry(
                    fields["sequence"],
                    fields["previous_hash"],
                    fields["event"],
                    cast("dict[str, object]", fields["payload"]),
                    fields["digest"],
                )
            )
        result = tuple(entries)
        verify_entries(result)
        return result
    except (ValueError, TypeError) as exc:
        raise AuditIntegrityError("audit_parse_invalid") from exc
