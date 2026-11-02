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
