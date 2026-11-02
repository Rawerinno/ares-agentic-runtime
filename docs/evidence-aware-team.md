# Experimental evidence-aware three-agent review

This separate research path uses three **real, distinct model invocations**
when `--live` is enabled. Each is non-executable, and every proposal
is measured against deterministic evidence/risk policy:

1. **Investigator** proposes a bounded evidence follow-up.
2. **Planner** proposes a bounded incident-window risk response.
3. **Critic** evaluates whether the previous two proposals match
   the trusted evidence and risk rules; it may return `inconsistent`.

Unlike the legacy fail-fast team, **all three roles run even when an
earlier model response is rejected**. This is intentional for research:
an untrusted proposal is never executed and the critic's ability to
recognize mistakes can now be assessed rather than hidden behind
an earlier rejection. A "consistent" critic response never overrules
deterministic governance. Every result stores only allowlisted category
values and fixed diagnostic codes.

Offline test (no model, no sensors):

```powershell
uv run python -m ares.runtime.evidence_team_acceptance --output ares-evidence-team-offline.json
```

Optional local Llama experiment:

```powershell
uv run python -m ares.runtime.evidence_team_acceptance --live --model llama3.2:3b --output ares-evidence-team-live.json
```

The experimental benchmark reports acceptance separately for all
three roles and records `critic_correctly_detected_bad_peers`
versus `critic_missed_bad_peers`. The deterministic policy remains
authoritative regardless of model success. All input histories are
synthetic; their limits are not validated for physical installations.
This path does not replace the existing persistent SQLite workflow,
does not issue tool calls to models, and has no authenticated control
or operator approval system.

## Blind independent critic review

A critic that can read the governor's `accepted` or `policy_mismatch` verdicts is only parroting the answer key. The reviewer context therefore contains only the two allowlisted prior proposals plus the trusted risk/evidence state, not earlier validation outcomes or expected labels. The reference critic independently recomputes policy agreement from trusted context. Test fixtures assert that accepted/rejected annotations are not leaked into critic prompts. Model performance must still be established empirically; no live-model success is claimed for this change.

## Durable local report audit (experimental)

`DurableEvidenceStore` is a **separate** local SQLite audit store for
bounded, simulated three-agent evidence reviews. A task is claimed
transactionally and its request digest binds the supplied ordered
readings and a caller-provided model/team identity. Completed reports
replay without model calls. Different readings or model identity under
the same task ID are rejected. Non-finite telemetry is canonicalized
for hashing and remains classified as invalid by the safety policy.
A cryptographic checksum detects accidental report corruption, but
is not a digital signature and cannot prevent database tampering.

The store has explicit failed-task recovery (up to three attempts).
A claim left `running` after a host crash cannot be automatically
taken over: an operator-controlled reconciliation is required, rather
than unsafe silent replay. Individual model exceptions still produce
a governed rejected advisory report.

Offline example (no Ollama or external hardware):

```powershell
uv run python -m ares.runtime.evidence_team_durable_demo --db .ares-evidence-test.sqlite --task-id demo-01 --temperatures 65 70 75
```

Running that command again with the same arguments replays the stored
output. This path does not implement distributed execution, trusted
multi-user audit, signed records, or actuator access, and it does not
replace the existing persistent incident runtime.

## Stricter audit replay invariants

The completed report decoder checks more than a matching hash: only known risk/evidence states, policy actions, role categories, diagnostics, role acceptance relationships and governed risk-action combinations may be replayed. This prevents accidental or malformed stored records, even when an invalid record has a recomputed checksum, from being treated as valid governed output. **This is still not tamper-proof authentication:** an adversary with filesystem and database access can edit both the payload and checksum or substitute an entirely valid-looking report. Durable audit integrity against privileged attackers would require signed external event logs, trusted key custody and deployment-specific threat modeling.
