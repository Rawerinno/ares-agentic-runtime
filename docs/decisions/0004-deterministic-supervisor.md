# ADR 0004 — Deterministic Supervisor MVP

Status: Accepted

## Decision

A first supervisor classifies simulated sensor readings through the existing
allowlisted read gateway. Thresholds are configurable and validated. It returns
immutable assessments with descriptive recommendations, never commands.

## Boundaries

- No model-generated plans or external LLM calls.
- No writes, auto-remediation, external tool execution or approval bypass.
- Unknown/unhealthy readings produce critical assessments.
- Denied gateway access fails the task instead of inventing observations.
- A completed task means assessment completed, not that an anomaly is resolved.

This creates a reliable baseline for later agent evaluations and real-model
decision-making.
