# ADR 0003 — Simulation-only read gateway

Status: Accepted

## Decision

The first tool boundary is an in-process, explicitly registered, read-only
gateway. Every invocation requires an agent ID and an allowlisted read capability.
High-risk requests fail closed even if a matching raw Approval exists elsewhere.

## Non-goals

This is not yet an MCP server and does not accept remote connections or
arbitrary tool handlers. No device writes and no real hardware adapters.
The next phase may introduce MCP transport only behind the same policy checks.

## Verification

Tests assert allowed reads, denied reads that do not reach sensor code,
high-risk rejection, unknown tool rejection, and execution integration.
