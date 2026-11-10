# ARES — Agentic Runtime for Engineering Systems

ARES is an engineering-focused agentic runtime for monitoring, diagnosing, and safely operating simulated and physical systems.

The project is being built as a production-oriented reference architecture rather than a chatbot demo. The long-term target is an auditable runtime where AI agents interact with engineering systems through explicit tools, safety policies, human approvals, persistent execution, and measurable evaluations.

## Current status

**Experimental local bounded-agent research prototype.** The repository now
includes a deterministic simulator and supervisor, safety policies, explicit
read-only integration boundaries, audit-chain utilities, locally evaluated
Ollama proposals, repeatable offline tests, and a small three-role pipeline.

The bounded three-role demonstration consists of:

1. An Ollama-backed temperature extractor.
2. An Ollama-backed arithmetic summarizer.
3. A deterministic reviewer that independently verifies results and applies
   temperature thresholds.

These are **roles in a controlled pipeline**, not three autonomous LLMs.
They execute sequentially by default. Concurrency for independent extraction
can only be enabled through a deliberately conservative benchmark-evidence gate.
Safety classification never depends on the model's classification.

### Durable incident workflow (experimental MVP)

The repository now includes a read-only simulated incident workflow that
coordinates four explicit roles: observer, diagnostician, planner and
deterministic safety reviewer. It persists task status and completed
reports locally with SQLite, supports idempotent replay and bounded
explicit recovery, and can optionally attach a strictly validated
proposal-only Ollama advisor. These are role handoffs in one process,
not independently deployed autonomous agents.

```powershell
uv run python -m ares.runtime.demo --task-id mvp-demo-001 --temperature 85
uv run python -m ares.runtime.dashboard
uv run python -m ares.runtime.mvp_evaluation --scenarios 60
```

The dashboard is a static HTML file; it is not an HTTP service. The
evaluation exercises simulated reference-model cases, failure recovery,
permission denials, and replay — not actual Ollama capability.
See [`docs/multi-agent-mvp.md`](docs/multi-agent-mvp.md).

### Why the scope is deliberately small

The local Llama 3.2:3B model returned 9/9 correct extraction and 9/9
correct simple arithmetic answers, but only 3/9 correct threshold classifications
on fixed repeated probes. It consistently treated warning and critical readings
as normal. The runtime therefore refuses to grant it safety or actuator authority.
The samples do not establish general reliability or real-time behavior.

### Local demonstrations

With Ollama and the `llama3.2:3b` model installed:

```powershell
uv run python -m ares.evaluation.bounded_team 55 60 65 --model llama3.2:3b
uv run python -m ares.evaluation.bounded_team 80 85 90 --model llama3.2:3b --audit-file .ares-bounded-audit.jsonl
```

Optional local audit entries form a validated SHA-256 hash chain and contain
decision codes and timings, not full prompts or sensor measurements. The chain
detects alterations of stored records but does not provide digital signatures
or prevent removal/replacement of the complete audit file.

### Offline scheduling decision

```powershell
uv run python -m ares.evaluation.concurrency_policy --candidate 2
```

Without adequate benchmark evidence, the result is sequential. See
[`docs/ollama-capability-boundary.md`](docs/ollama-capability-boundary.md)
and [`docs/bounded-scheduling.md`](docs/bounded-scheduling.md).

**Not production-ready:** physical device writes, autonomous programming,
persistent multi-LLM collaboration, web operations UI, and hard real-time
guarantees remain outside the validated scope.

## Planned capabilities

- Device simulation and fault injection
- MCP-based device integration boundary
- Supervisor agent for diagnostics and operations
- Human approval for high-risk actions
- Durable execution, retries, and idempotency
- Trace-based observability and reliability metrics
- Automated evals for tool use, recovery, and safety
- Web operations console
- Physical ESP32/Arduino integrations

## Engineering principles

1. Agents never talk directly to device implementations.
2. Read and write capabilities are explicit and separately permissioned.
3. High-risk actions require human approval.
4. Every action should be traceable and testable.
5. Failures are first-class scenarios, not edge cases.
6. Single-agent performance is measured before multi-agent complexity is introduced.

## Development

Requirements:

- Python 3.13
- uv

Install the locked development environment:

```bash
uv sync --dev --frozen
```

Run the quality gates:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv build
```

## Release candidate evidence (simulation-only)

The offline acceptance gate runs on Ubuntu and Windows in CI. To reproduce it
locally, use Python 3.13 and `uv` from a clean checkout of the candidate commit:

```powershell
uv sync --dev --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
uv run --frozen pytest
uv run --frozen python -m ares.evaluation.release_acceptance --output ares-release-acceptance.json
uv build
```

Inspect the JSON report before accepting a candidate. Require
`scope == "offline_stub_only"`, `all_passed == true`,
`device_actions == "disabled"`, `default_parallelism == 1`, and
`scenario_count == 121`. The report contains simulated model calls, not
measured Ollama inference. The command exits nonzero on failed checks; a
successful CI job is necessary but **not** proof of live-model reliability.

For the optional local Ollama demonstration, run the two bounded-team examples
above with `llama3.2:3b` and record the exact model version, command, exit
status, outputs, and date. Treat all LLM suggestions as untrusted and advisory.
Compare any proposed live-model change against a paired baseline using the
existing acceptance comparator before considering integration. A worse live
acceptance rate is a regression even if deterministic governance still passes.
Do not infer hardware safety from simulated results.

A candidate is **not ready** if any required CI check fails, if the offline
acceptance report fails, if device actions become enabled, or if safety
classification is delegated to a model. Document any missing local-model
results explicitly as *not run*; do not substitute synthetic measurements.

## Architecture

The initial system architecture is documented in [`docs/architecture.md`](docs/architecture.md). Significant technical decisions are recorded as ADRs under [`docs/decisions/`](docs/decisions/).
