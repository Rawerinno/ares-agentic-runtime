# ARES — Agentic Runtime for Engineering Systems

ARES is an engineering-focused agentic runtime for monitoring, diagnosing, and safely operating simulated and physical systems.

The project is being built as a production-oriented reference architecture rather than a chatbot demo. The long-term target is an auditable runtime where AI agents interact with engineering systems through explicit tools, safety policies, human approvals, persistent execution, and measurable evaluations.

## Current status

**Phase 1 — Platform Foundation**

The repository currently establishes the engineering baseline: reproducible Python environments, strict static analysis, automated tests, CI, and architecture decision records.

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

## Architecture

The initial system architecture is documented in [`docs/architecture.md`](docs/architecture.md). Significant technical decisions are recorded as ADRs under [`docs/decisions/`](docs/decisions/).
