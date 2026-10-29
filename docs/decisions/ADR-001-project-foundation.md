# ADR-001: Project Foundation

- **Status:** Accepted
- **Date:** 2026-10-29

## Context

ARES will combine an agent runtime, MCP integrations, simulation, safety controls, evaluations, and later physical-device adapters. The project needs a reproducible Python foundation that supports strict quality gates without coupling the runtime to a developer workstation.

## Decision

ARES will use:

- Python 3.13 as the runtime baseline.
- `uv` for Python installation, virtual environments, dependency resolution, and lockfiles.
- A `src/` package layout with the import package named `ares`.
- Ruff for linting and formatting checks.
- Pyright in strict mode for static type checking.
- pytest and pytest-cov for automated testing and coverage measurement.
- GitHub Actions for CI on pushes to `main` and pull requests.
- Architecture Decision Records for material technical decisions.

## Rationale

A `src/` layout prevents accidental imports from the repository root and makes package behavior closer to installed production behavior. A committed lockfile makes local and CI environments reproducible. Strict linting, typing, and tests establish quality constraints before agentic behavior introduces nondeterminism.

## Consequences

All code merged into `main` is expected to pass the same automated quality gates locally and in CI. Dependencies must be added through `uv` so the lockfile remains authoritative. Changes that materially alter architecture should add or supersede an ADR.
