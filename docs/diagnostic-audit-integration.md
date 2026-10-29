# Diagnostic audit integration

ARES CLI diagnostics now include `audit_digest` and `audit_sequence` from an
in-memory SHA-256 chained event. The structured event records the numeric
reading, sensor health, supervisor severity, governed recommendation, model
status/category and consistency finding codes. It intentionally omits raw
prompts and rationale. This is **not persisted** by the CLI; no audit log file
is silently written to your computer.

It proves that one JSON-like event was hashed, not that the reading was
truthful, the event was securely stored or an attacker cannot replace the
entire chain. Long-term tamper evidence will need an external trusted anchor.
