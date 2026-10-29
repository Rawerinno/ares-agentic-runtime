# Opt-in local audit persistence

The CLI can store a hash-linked event chain in a local JSONL file:

```powershell
uv run python -m ares.intelligence.ollama_demo --live --temperature 85 --audit-file .ares-local-audit.jsonl
uv run python -m ares.intelligence.ollama_demo --live --temperature 20 --audit-file .ares-local-audit.jsonl
```

Without `--audit-file`, **no file is written**. Existing records are checked
before extension; malformed chains are rejected. The file is rewritten using
an atomic replacement in the same directory, including an fsync of its contents.

Security scope: trusted **single-writer** local use only. Atomic replacement
does not provide locking, trusted timestamps, signing, durability against all
power-loss scenarios or defense against whole-file replacement/rollback. Use
a path outside shared/public folders; do not store secrets or raw model text.
A long-term trusted audit design requires access controls and an external anchor.
