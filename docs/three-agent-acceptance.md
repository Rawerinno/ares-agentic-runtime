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
