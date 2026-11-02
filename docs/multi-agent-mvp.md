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

## Read-only operations view

After running one or more simulated incident tasks, export a local HTML report:

```powershell
uv run python -m ares.runtime.dashboard --db .ares-incident-tasks.sqlite3 --output ares-operations.html
```

Open `ares-operations.html` in a browser. It displays total completed,
normal/warning/critical breakdown, running/failed task counts, individual
incidents, and expandable deterministic/model advisory handoffs.

This is a **static, local-only, read-only export**. No HTTP listener,
JavaScript, external resources, sensitive credentials or physical device
controls are provided. All stored text is HTML-escaped and the document
uses a restrictive Content Security Policy. It is not an authenticated
operations service and does not auto-refresh.

## Automated offline MVP acceptance

```powershell
uv run python -m ares.runtime.mvp_evaluation --scenarios 60 --output ares-mvp-evaluation.json
```

This evaluates 60 deterministic simulated incidents: 20 normal, 20
warning, and 20 critical. Every task gets an advisory handoff (a
local reference model or a deliberately malformed proposal), a
deterministic safety review, an immutable SQLite record, and an
idempotent replay. Additional tests inject a persistent sensor fault,
attempt recovery until the three-attempt budget is exhausted, and
check that an unauthorized agent cannot read the gateway.

The JSON report includes total scenarios, correct classifications,
role handoffs, correctly rejected model proposals, severity counts,
idempotent replays, failure-recovery checks, mean/median/p95 execution
latencies, and a clear `offline_simulation_reference_model` scope.

The test uses **no Ollama** and does not validate real-device
performance. A local end-to-end session with the actual Llama model
will be requested only once the remainder of the MVP is consolidated.

## Three governed LLM roles — opt-in experimental mode

The CLI can now coordinate **three separate LLM invocations** on the
same local Ollama model. They are sequential (not three separate model
processes), carry distinct prompts and strictly validated outputs:

1. Investigator proposes a bounded hypothesis (`stable`,
   `thermal_load`, or `sensor_fault`).
2. Planner proposes a bounded **non-executable** action category
   (`monitor`, `inspect`, or `human_review`).
3. Critic checks consistency with trusted telemetry and earlier
   validated agent handoffs. It cannot approve an actuator command.

The Python supervisor alone owns temperature severity, the permitted
response and the final safety review. Any model mismatch, malformed
JSON, model exception, or disagreement fails closed and is recorded as
a coded handoff; the incident remains persisted with its deterministic
outcome. Role outputs never become tool invocations. Completed tasks
replay without model calls, and task identity binds the team mode and
model name.

Run a **zero-model reference** demonstration:

```powershell
uv run python -m ares.runtime.demo --temperature 65 --task-id team-offline-01 --team offline
```

After CI approval, the local Ollama demonstration:

```powershell
uv run python -m ares.runtime.demo --temperature 65 --task-id team-llama-01 --team ollama --model llama3.2:3b
```

The second command uses the user's installed local Ollama server.
The model can fail any of the three contracts and the report will
show the rejection without affecting the deterministic safety outcome.

This is **three functional LLM agents under a single governed process**,
not distributed or continually autonomous workers. The capability,
latency, and reliability of the actual three-agent Llama setup remain
to be measured locally. It is not an authorized hardware controller.
