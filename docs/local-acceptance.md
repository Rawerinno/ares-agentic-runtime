# ARES — Consolidated local Ollama acceptance

This is the first *single-command* real-model acceptance session for the
bounded local ARES runtime. It uses the existing Ollama installation.
No third-party API keys, cloud model or physical sensor is required.

## Run after CI has merged the change

On the laptop with Ollama running:

```powershell
cd C:\Dev\ares-agentic-runtime
git switch main
git pull
uv sync --dev --frozen
uv run python -m ares.evaluation.local_acceptance --model llama3.2:3b --repeats 2 --output ares-local-acceptance.json
```

The benchmark uses nine fixed small scenarios, each repeated twice.
It makes up to **90 local model calls**: 3 extractions, 1 arithmetic
calculation, and 1 independent arithmetic review per scenario. A rejected
case skips later model roles. The run does not make any device changes.

The JSON distinguishes:
- **Scenario acceptance:** all three roles agree with Python's reference.
- **Role accuracy:** exact numeric correctness of extractor, arithmetic,
  and independent reviewer, each with the number of attempts shown.
- **Latency:** mean, median and maximum by role, and total wall-clock time.
- **Failure count:** rejected scenarios, errors, and mismatched responses.
- **Safety authority:** classification always comes from deterministic Python.

This evaluation is sequential by design; it is not a speedup benchmark.
The fixed set of nine prompts and two repetitions is a useful smoke test,
**not statistically sufficient evidence for generalization or safety**.

The script exits with code 1 if any scenario fails; the JSON report is
still saved for inspection. Do not re-run until it passes: failures are
valuable evidence that should inform the next change to the runtime.
