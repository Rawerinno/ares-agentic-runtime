# ARES Multi-Agent MVP 0.1 — simulated incidents

This proof-of-concept coordinates **four bounded software roles**:
observer (authorized read through the gateway and deterministic supervisor),
diagnostician (interpret the supervisor's severity), planner (propose
human investigation), reviewer (enforce no automatic actuation). These are
deterministic roles, **not four autonomous language models**. The design
intentionally contains no model, hardware write, API charges or remote
tools.

## Durable execution

A standard-library SQLite task store records a task identifier, an
immutable completed report, status, request binding, and number of
attempts. SQLite claims use `BEGIN IMMEDIATE`. Replaying a completed
task returns the stored report and does **not reread the sensor**.
Unfinished or failed tasks do not automatically restart. An operator
must select `--recover`, which permits at most three total attempts.

Failure or crash after claiming a task but before completion leaves an
unfinished row to recover explicitly. This is single-host development
persistence, not exactly-once distributed execution, and not protected
against malicious database editing. Two actors using the same task ID
must not change their request parameters. Input provenance beyond
agent/tool IDs is not implemented, so the simulation is not yet suitable
for untrusted remote callers.

## Demo

```powershell
uv run python -m ares.runtime.demo --temperature 85 --task-id incident-001
uv run python -m ares.runtime.demo --temperature 85 --task-id incident-001
uv run python -m ares.runtime.demo --temperature 62 --task-id incident-002
```

A SQLite file `.ares-incident-tasks.sqlite3` appears in the current
directory. The first and second commands return the identical report
for `incident-001`, demonstrating idempotent replay. A warning task
creates a separate stored record. The output lists four handoffs,
severity, `review_required` or `investigation_recommended`, and the
explicit `device_actions: disabled` boundary.

The command is a reproducible engineering demonstration, **not**
a production service or user-facing control plane. Further milestones
include signed/trusted approvals, external integrations, failure-injection
and multiple agent processes, authenticated APIs, and operations UI.

## Optional proposal-only model advisor

The deterministic observer/diagnostician/planner/reviewer workflow now
supports an optional additional `model_advisor` role. This role uses
the existing strict `BoundedProposalEngine`, which only accepts
`observe`, `investigate`, or `request_review` and rejects any
attempt to change authoritative severity. Rejected or unavailable
models leave the deterministic incident report intact and store a
coded advisory failure. The model cannot access any tool from this
workflow.

```powershell
uv run python -m ares.runtime.demo --temperature 85 --task-id offline-advice --advisor offline
uv run python -m ares.runtime.demo --temperature 85 --task-id local-llm-advice --advisor ollama --model llama3.2:3b
```

Only the second command invokes the local Ollama model. A new task ID
is required when changing advisory mode, because a completed task
is immutable. The same task ID always replays a previously completed
report instead of invoking the model again. None of these commands
write to equipment or grant human approval.

The added `model_advisor` is an advisory role in one Python process.
This is not yet a persistent process-per-agent or distributed multi-LLM
orchestrator. The real Ollama advisory path remains to be tested in
the user's eventual consolidated local acceptance session.
