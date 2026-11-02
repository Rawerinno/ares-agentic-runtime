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
