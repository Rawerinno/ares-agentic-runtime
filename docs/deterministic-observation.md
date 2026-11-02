# ARES — Verified observations with deterministic arithmetic

The November 2026 local acceptance benchmark provided **real model evidence**:

| Local measurement | Result |
| --- | ---: |
| Complete scenarios | 14/18 (77.78%) |
| Extracted values | 54/54 (100%) |
| Arithmetic answers | 14/18 (77.78%) |
| Independent reviewer | 14/14 on accepted scenarios only |
| Transport errors | 0 |
| End-to-end runtime | 100,257.39 ms |

The same arithmetic task failed in both repetitions of the negative
case (`-8, -4, 0`) and both repetitions of the warning decimal case
(`61.5, 62.5, 63.5`). The independent reviewer was not called for
these failures, so its 14/14 score is **selection-biased** and cannot
demonstrate recovery ability.

**Architectural change:** calculate means and classify temperatures in
trusted Python. Use the local model only to propose extracted readings,
which are checked against strict input parsing. Optional model arithmetic
is diagnostic and cannot override Python. A wrong optional calculation
is recorded as `advisory_arithmetic_mismatch` but does not turn a
correct deterministic outcome into an incorrect safety decision.
An incorrect extraction always rejects the observation.

### Read-only local example

```powershell
uv run python -m ares.evaluation.bounded_observation 61.5 62.5 63.5
uv run python -m ares.evaluation.bounded_observation -8 -4 0 --input-mode llm --evaluate-arithmetic
```

This uses the localhost Ollama model `llama3.2:3b`, with no API charges
or physical device actions. Outputs distinguish `status`,
`verified_mean`, `severity`, and optional
`advisory_correct`. If a model answer is wrong, it is never
treated as authoritative.

The prior `bounded_team` module and the `local_acceptance`
benchmark are intentionally retained to measure raw-model failure
rather than conceal it. Future acceptance reports also include the
actual `model_mean` and `expected_mean` so failures can be
diagnosed without guessing their values.

This is a narrow research prototype. The 54/54 extraction score on
these nine small cases does not prove general text extraction quality.
Real device control and autonomous actions remain disabled.

## Structured-input fast path (default)

For machine-readable numeric fields, **do not involve an LLM**. The
`bounded_observation` CLI now defaults to `--input-mode structured`,
which validates three bounded Celsius readings, calculates the exact mean,
and classifies it entirely in Python.

```powershell
uv run python -m ares.evaluation.bounded_observation -8 -4 0
uv run python -m ares.evaluation.bounded_observation 61.5 62.5 63.5
```

These commands require **zero model calls**, work even if Ollama is offline,
and report `input_mode: structured`, `model_authority: none`,
`model_calls: 0`, and a measured wall time. Inputs must use a strict
finite bounded numeric representation. For comparative LLM evaluation,
select `--input-mode llm` explicitly; `--evaluate-arithmetic` is
only accepted in that mode.

The previously measured 5.50s and 2.58s durations apply to the
four-call LLM-enabled experiments. They are **not** measured speedups
for the new structured fast path; record actual local timings before
claiming a particular improvement.
