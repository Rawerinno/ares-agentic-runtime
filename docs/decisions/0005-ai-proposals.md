# ADR 0005 — Proposal-only model boundary

Status: Accepted

## Decision

Model outputs are untrusted data. A provider-independent ModelAdapter returns
data validated by ProposalEngine into a small, immutable Decision contract.
Proposals do not contain tool calls, execution code, or actuator arguments.

The deterministic Supervisor remains the source of observed severity. A model
cannot downgrade it, dismiss warning conditions, or avoid human review of
critical conditions.

## Scope

No hosted model, API key or external AI calls are required in this phase.
The interface is ready for a future provider adapter but cannot perform
control actions or grant itself tool permissions.
