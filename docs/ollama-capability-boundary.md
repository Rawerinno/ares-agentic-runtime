# Local Ollama capability boundary (experimental)

The purpose of this probe is **not** to maximize apparent agent ability. It
determines a small, measured boundary for simple engineering tasks before
any multi-agent execution is enabled.

## Run on the computer with Ollama installed

```powershell
ollama list
uv sync --dev --frozen
uv run python -m ares.evaluation.ollama_capability_boundary --model llama3.2:3b --repeats 3 --output capability-report.json
```

The evaluator sends requests only to `127.0.0.1:11434` and **never executes
model-produced commands**. It uses deterministic sampling, short structured
answers, a response size limit, and a timeout. Results contain test prompts
and model answers, so keep the JSON locally if it may contain sensitive data.

### Progressive tiers

1. Extract a single temperature measurement from short text.
2. Calculate a simple arithmetic mean from three measurements.
3. Classify measurements at the normal/warning/critical thresholds.

Every case is repeated independently (default: three times). A tier passes
only if raw answer accuracy is at least 90% **and** every case gives exactly
the same answer across repetitions. A failing tier stops the run immediately.
A transport or parsing exception counts as a wrong answer.

`highest_passing_tier` is a *measured test outcome*, not a capability
certificate. The prompts are fixed and limited; a passing tier does not
guarantee success on new tasks or adversarial inputs. Do not enable device
writes, automatic approvals or autonomous code changes based on this report.

The existing governed safety benchmark is a separate measurement and must
not be substituted for raw model competence.

## Multi-agent next step

After reviewing real local results, build a bounded three-role pipeline
(interpret → propose → review) **only for tasks within the measured boundary**.
Keep final decisions deterministic, use read-only tools, record disagreements,
and stop safely if confidence or model consistency deteriorates. On a laptop,
concurrent Ollama calls may serialize or exhaust memory; benchmark concurrency
before enabling parallel dispatch.
