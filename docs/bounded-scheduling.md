# ARES bounded scheduling: measured evidence and operational limits

## Evidence recorded on 2 November 2026

All values below were reported from local Ollama (`llama3.2:3b`) on the
developer's laptop, not reproduced by GitHub Actions. They are small
experimental samples, **not** model accuracy guarantees.

| Experiment | Sequential | Concurrent |
| --- | ---: | ---: |
| Three concurrent requests, calls per mode | 12 | 12 |
| Accuracy (3-way) | 12/12 | 12/12 |
| Model errors (3-way) | 0 | 0 |
| Mean latency per call (3-way) | 1,850.52 ms | 3,774.44 ms |
| Wall time (3-way) | 22,206.54 ms | 17,759.46 ms |
| Speedup (3-way) | baseline | 1.250x |
| Two concurrent requests, calls per mode | 18 | 18 |
| Accuracy (2-way) | 18/18 | 18/18 |
| Model errors (2-way) | 0 | 0 |
| Mean latency per call (2-way) | 925.31 ms | 2,185.97 ms |
| Wall time (2-way) | 16,655.90 ms | 21,193.94 ms |
| Speedup (2-way) | baseline | 0.786x |

The two experiments have different run lengths and environmental
conditions, so **2 versus 3 concurrent requests are not directly
comparable**. In both experiments each concurrent response was slower
on average, even when the 3-way batch completed sooner overall.

Earlier model-boundary evaluation:
- Extraction: 9/9 responses correct on three fixed cases.
- Arithmetic: 9/9 responses correct on three fixed cases.
- Direct safety classification: 3/9 responses correct; 60 and 80 C
  were repeatedly returned as normal.

Therefore: **LLM extraction and arithmetic are advisory only.**
Temperature classification and escalation remain deterministic and
never follow an LLM-provided safety label.

## Conservative scheduler

The default mode is one local model request at a time. This is
deliberate, because one fast 3-way trial and one slower 2-way trial do
not support enabling either as a production default.

`ares.evaluation.concurrency_policy` is a pure Python evidence gate.
It evaluates independent benchmark JSON reports *without calling a
model* and recommends a candidate concurrency only when all conditions
hold:

1. Three or more **distinct** raw-model benchmark reports for the same
   candidate parallelism.
2. Every sequential and parallel attempt in every report was correct,
   with no model errors.
3. Identical task counts within each report and across trials.
4. Every trial achieved at least 1.15x speedup (not just the average).
5. All data has the expected shape. Missing, malformed, inconsistent
   or duplicated evidence always causes a sequential recommendation.

To see the current safe recommendation (no reports, no LLM calls):

```powershell
uv run python -m ares.evaluation.concurrency_policy --candidate 2
```

The bounded three-role demo uses this policy when optional
`--benchmark-report` files are supplied; a `--candidate` flag alone
never authorizes parallel work. For example, **later**, after collecting
three qualifying independent reports:

```powershell
uv run python -m ares.evaluation.bounded_team 55 60 65 --candidate 2 --benchmark-report trial1.json --benchmark-report trial2.json --benchmark-report trial3.json
```

Without valid evidence the demo uses sequential extraction, regardless
of the requested candidate. Its arithmetic stage is also sequential;
only three independent extraction calls may overlap. The deterministic
reviewer always validates the extracted values, independently
recomputes the mean, and applies the safety thresholds.

Concurrency is bounded to three for the demo; it is not a guarantee
that three LLM instances are executing simultaneously. Ollama may
serialize requests or exhaust device resources. The existing local
transport has socket timeouts but not a strict interrupt mechanism for
all blocking I/O; do not interpret this as a hard real-time guarantee.

## Further evaluation before enabling concurrent execution

The next local test session should collect a paired, randomized-order
series (sequential, parallel 2, parallel 3), including model warmup,
several independent repetitions, peak RAM, individual request latency,
total wall time, accuracy, error rate and any timeout. Comparing
different run lengths or warm/cold states risks attributing noise to
concurrency.

All real-model tests are deferred until a substantial release
candidate is ready; offline GitHub CI continues meanwhile.
