# ARES diagnostic audit chain — prototype

The `ares.evaluation.audit` module provides immutable-looking in-memory
entries with ordered sequence numbers, SHA-256 digests and a previous-digest
chain. It supports JSONL serialization and validation. It is deliberately
storage-independent, performs no file writes, and makes no network calls.

Example:

```python
from ares.evaluation.audit import append_entry, to_jsonl, from_jsonl

entries = append_entry((), "diagnostic", {"severity": "critical"})
content = to_jsonl(entries)
assert from_jsonl(content) == entries
```

**Security limitations:** A hash chain detects modification, deletion of
intermediate entries and reordering *within a supplied chain*. It cannot
detect an attacker who replaces the entire chain or truncates its tail.
There is no trusted anchor, digital signature, append-only filesystem,
identity, durable persistence, timestamp authority or protection against
secret leakage. Do not record credentials, personally identifying
information or raw model prompts. Operational audit logging requires a
separate trusted persistence and anchoring design.

No LLM or simulated equipment has authority to write to this module's
repository or execute device commands.
