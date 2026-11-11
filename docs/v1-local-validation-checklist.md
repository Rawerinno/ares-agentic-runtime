# ARES v1.0 — concentrated local validation checklist

This checklist is for the operator's **final** local validation after the
simulation-only CI candidate has passed. It is not evidence of a completed
local test. Run from a clean checkout of the **exact candidate commit**,
record its full SHA, date, OS, Python version, uv version, and Ollama model
identifier. Do not connect physical devices or enable actuator/write tools.

## 1. Establish the candidate and offline baseline

```powershell
git fetch origin
git switch main
git pull --ff-only
git rev-parse HEAD
uv sync --dev --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
uv run --frozen pytest
uv run --frozen python -m ares.evaluation.release_acceptance --output ares-release-acceptance.json
uv run --frozen python -m ares.evaluation.verify_release_report ares-release-acceptance.json
uv build
```

Record each exit code and preserve the unmodified JSON report. Required
report invariants: `scope=offline_stub_only`, `all_passed=true`,
`device_actions=disabled`, `default_parallelism=1`, and
`scenario_count=121`. These tests use simulated calls, **not** Ollama.

## 2. Verify Ollama availability without devices

```powershell
ollama --version
ollama list
ollama show llama3.2:3b
```

If the model is absent, mark live validation **not run**; do not substitute
synthetic outputs. Keep the model identifier and version in the evidence.

## 3. Run two advisory-only live examples

```powershell
uv run --frozen python -m ares.evaluation.bounded_team 55 60 65 --model llama3.2:3b
uv run --frozen python -m ares.evaluation.bounded_team 80 85 90 --model llama3.2:3b --audit-file .ares-bounded-audit.jsonl
```

Capture stdout, stderr, exit status, and execution time for each command.
The deterministic reviewer must remain authoritative for warning/critical
classification; model responses are proposals, not permission to act.
Preserve the audit file and check its chain using the repository's documented
audit validation interface before declaring evidence complete.

## 4. Compare live acceptance with the historical baseline

Historical reference only: 5/18 unsupervised correct versus 18/18 with
deterministic supervision; the rejected PR #100 yielded 4/18 unsupervised.
These are **not** measurements from this run. If running the repository's
live evidence-acceptance evaluation, use the documented invocation for the
candidate commit and a paired baseline with the **same model, prompts,
scenarios, sampling configuration and environment**. Record raw correctness,
supervised correctness, model errors, rejected responses, latency and
follow-up confusion. Do not claim improvement from incomparable runs.

## 5. Release decision

Mark the candidate **blocked** if any required offline check fails, the
persisted report fails verification, any device action becomes enabled,
the deterministic safety reviewer is bypassed, or a live acceptance
regression is detected. A missing live run is **not run**, not **passed**.
Keep the commit SHA, CI URLs, local command transcript, JSON outputs and
limitations together. No physical-device, destructive or real-time safety
claim is supported by this checklist.
