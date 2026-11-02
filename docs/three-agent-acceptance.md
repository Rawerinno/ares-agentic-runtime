# Three-agent governed acceptance

The ARES runtime can coordinate three distinct model invocations
(investigator, planner and critic) in a single Python process. Their
proposals never change the deterministic supervisor severity, and no
hardware action is authorized. This is not distributed or continuously
autonomous execution.

## Offline acceptance (CI-friendly)

```powershell
uv run python -m ares.runtime.three_agent_acceptance --repeats 2 --output ares-three-agent-offline.json
```

This runs nine fixed simulated incidents twice, including the warning
and critical thresholds and invalid sensor telemetry. It needs no
Ollama service. The deterministic reference role generator is **not**
a real model; its role acceptance is only a contract and integration
check.

## Local real-model acceptance

Once the code is merged, the consolidated Llama 3.2:3B test is:

```powershell
uv run python -m ares.runtime.three_agent_acceptance --live --model llama3.2:3b --repeats 2 --output ares-three-agent-live.json
```

There are 18 scenarios and at most 54 **sequential** Ollama calls.
Malformed output or a wrong answer is not retried or silently replaced;
downstream model roles are skipped after a rejection. Every run still
produces a deterministic incident classification and a persisted result
in temporary SQLite storage. The test does not need paid APIs or
physical sensors.

The machine-readable report separates:

- `governed_correct`: correct deterministic outcomes regardless of model quality
- `full_team_accepted`: scenarios where all three independent model-role contracts passed
- `role_metrics`: attempts, accepted responses, model errors and latency for each role
- `idempotent_replays`: completed tasks returned without model invocation
- `results`: per-scenario role calls and redacted error codes

The command exits nonzero only if the governed safety or idempotent
replay checks fail. Poor model-role accuracy is **reported** and is not
hidden by deterministic fallbacks. A 100% safety score on these fixed
simulator cases is not evidence of real-device safety, robust language
generalization, or independent agent autonomy. No external tools or
device writes are available to the models.

## Why the first live run stopped at the investigator

The first real local Llama test completed 18/18 deterministically governed
scenarios and 18/18 idempotent replays, but the investigator received
18 `policy_mismatch` rejections and the planner and critic were not
invoked. Transport errors were zero. The first report did **not**
record the raw answer, so the precise cause cannot be established from
that run alone.

Previously the generic capability-benchmark adapter requested an Ollama
JSON envelope with an `answer` **string**. The first agent was then
asked to put a second JSON object *inside that string*. This is a likely
source of failures on small local models.

The dedicated adapter now requests the role-specific JSON **object
directly** via Ollama structured `format` schemas. The governor still
enforces the authoritative field values and rejects incorrect, extra,
or malformed fields. No safety policy is relaxed to improve model scores.

The new local acceptance test should use the command above after
pulling the updated `main`. The benchmark records genuine model
acceptance separately from deterministic safety; early failures still
prevent downstream agents from running.

## Rejection analysis after the second live benchmark

On the second Llama 3.2:3B run, deterministic governance was 18/18 and
idempotent replay was 18/18; investigator acceptance improved to
10/18 (55.6%), planner acceptance was 0/10, and the critic never ran.
The previous reporting system only captured `policy_mismatch`, so it
was not possible to distinguish wrong severity from a wrong hypothesis,
wrong plan, invalid fields, or malformed JSON.

The next version uses **role-specific instructions** and preserves exact
deterministic rules. Its rejection codes now distinguish
`severity_mismatch`, `hypothesis_mismatch`, `plan_mismatch`,
`verdict_mismatch`, `invalid_types`, `invalid_fields`,
`invalid_shape`, `invalid_json`, and `oversized_response`.
A `rejection_counts` section aggregates these codes by role. It never
stores raw model responses, prompt content, or untrusted text. No
hardware writes, policy relaxation, or automatic retries were added.

A subsequent local run should use a **new output file**, for example
`ares-three-agent-live-v3.json`, to preserve the second benchmark.
Because the three calls remain fail-closed and sequential, later roles
may still show zero attempts if earlier roles fail. This is an honest
measurement limitation, not evidence that uninvoked roles are inaccurate.

## V4 evaluation: roles own proposals, ARES owns severity

The third local benchmark achieved 8/18 full-team acceptances (44.4%),
18/18 safe deterministic outcomes, 18/18 idempotent replays, and
8/8 accepted responses each from the planner and critic **conditional
on being invoked**. The investigator rejected ten outputs:
seven severity mismatches and three hypothesis mismatches.

The live CLI now defaults to a **role-only JSON contract**: an agent
outputs exactly one bounded value (`hypothesis`, `plan`, or `verdict`).
Severity remains in trusted, read-only context and is NEVER accepted
from the model. The deterministic supervisor still checks every
proposed value and controls the outcome. The redundant requirement
for models to echo the authoritative severity has been removed from
their output schema. The old two-field contract is still available
for benchmarking with `--role-contract legacy`; it is not a safety
authority.

For a consolidated investigation on local Ollama:

```powershell
uv run python -m ares.runtime.three_agent_acceptance --live --model llama3.2:3b --repeats 2 --probe-roles --output ares-three-agent-live-v4.json
```

The `--probe-roles` mode is **diagnostic only**. Beyond the normal
fail-closed sequential team run, it separately calls each target
model role once per scenario, substituting a deterministic reference
generator for the other roles to provide validated peer context.
This prevents a weak investigator from hiding planner/critic
competence. The report separates `role_metrics` (real collaboration)
from `isolated_role_metrics` (independent role probes). Each isolated
probe is still validation-only, with no device control, but success
in isolation is not evidence of reliable autonomous collaboration.

Each repetition may issue up to three sequential team model calls
plus three isolated model calls. With nine scenarios and two repeats,
the maximum is 108 local model calls (often fewer if the sequential
team rejects early). Choose `--repeats 1` for a smaller initial
sample. This is not a benchmark of general model intelligence.

## Hypothesis confusion audit

The benchmark includes bounded per-role proposed categories and an investigator confusion table derived from trusted scenario readings. Raw model-generated text is not stored in these fields. The synthetic `thermal_load` label is an evaluation category, not a proven physical cause from one temperature sample. No model proposal can change supervisor severity or actuate devices.
