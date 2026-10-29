# ADR 0002 — Explicit, fail-closed tool authorization

Status: Accepted for the simulation-only foundation.

## Context

ARES must distinguish observational reads from operations that modify a device.
A generative model is not a source of permission.

## Decision

- Grants match the exact agent ID, tool ID, and capability.
- No matching grant means DENY.
- Even if granted, WRITE and HIGH-risk operations require human approval.
- Authorization is represented by pure Python contracts and does not execute tools.
- Matching approval data is intentionally *not* proof of human identity.
- Real actions must remain unavailable until a trusted approval store, verification,
  one-time operation binding, audit log, expiry, and race-safe consumption exist.

## Consequences

The current policy is appropriate for isolated unit tests and simulated
read-only orchestration. It is not an authorization gateway for physical control.
