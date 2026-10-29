# Hypothesis catalogue (simulated telemetry)

Hypotheses are **not** equipment diagnoses. The catalogue returns only
non-actuating checks, marked `unverified`, when temperature exceeds the
configured warning threshold. It provides no causes for normal readings.
If the sensor reports unhealthy, independent measurement is prioritized.

The catalogue is deliberately deterministic. The LLM does not get to invent
operational actions or override the supervisor. Future real-world validation
requires additional independent measurements, calibration and expert review.

To view hypotheses, run:

```powershell
uv run python -m ares.intelligence.ollama_demo --live --temperature 85
```

Look for `hypotheses`, alongside `evidence` and `governed_proposal`.
