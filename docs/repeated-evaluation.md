## Repeated evaluation

Use `--repeats 3` to evaluate each of the six simulated temperatures three times. The report distinguishes raw LLM decisions (`passed`) from governed proposals (`governed_passed`), and includes average/median elapsed time, model errors and rejected responses. No inference is run in CI; the offline reference is used for tests.

```powershell
uv run python -m ares.evaluation.ollama_benchmark --live --model llama3.2:3b --repeats 3
```

A successful governed score should not be mistaken for LLM accuracy or industrial safety certification. Repetition improves measurement, not ground-truth validation.
