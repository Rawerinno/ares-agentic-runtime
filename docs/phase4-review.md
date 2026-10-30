# Phase 4 review — 30 October 2026

## Evidence

The consultant ran the grouped validation on Windows with `--live --preemptive --model llama3.2:3b --repeats 3`.

| Measure | Observed |
| --- | ---: |
| Batch acceptance checks | 6/6 |
| Fixed simulated scenarios | 18 |
| Raw LLM category matches | 6/18 |
| Governed category matches | 18/18 |
| Model errors | 0 |
| Rejected responses | 0 |
| Mean latency (ms) | 3869.62 |
| Median latency (ms) | 3539.56 |

The preceding local non-preemptive benchmark likewise obtained 6/18 raw and 18/18 governed matches. This sample is small and deterministic: it is not a statistically representative reliability measurement.

## What is supported

- Offline reference and fault-injection tests.
- Read-only sensor simulation and deterministic supervisor classification.
- Model errors can degrade to deterministic recommendations without authorizing device actions.
- Hash-linked local audit storage, cooperative writer lock, and atomic replacement checks.
- Process-isolated local Ollama calls with termination on timeout. Python process start and cleanup impose overhead; a deadline is not a hard real-time guarantee.
- Windows and Ubuntu CI checks for the above implementation.

## Remaining risks and limits

- The model itself matches the expected action only 33.3% of the measured cases.
- Governed agreement on six fixed input temperatures does not establish generalization.
- Model-generated prose and hypotheses are not fact-checked.
- Audit hashes are not signed or externally anchored; whole-file rollback and malicious filesystem access remain possible. A crashed writer can leave a lock requiring administrative recovery.
- No real equipment, actuator, PLC, hardware-in-the-loop, operator workflow or industrial safety certification has been tested.
- The process-isolated worker is opt-in; the original transport remains the default.
- Cross-platform process scheduling means the upper bound on total wall-clock completion (including worker cleanup) is not formally guaranteed.

## Gate decision

**Phase 4: simulated prototype validation provisionally accepted.** This is conditional on retaining the limitations above and continuing regression checks. It does not signify that deployment to actual equipment is approved.

## Proposed Phase 5 — controlled operational integration

1. Introduce a strictly read-only integration adapter and explicit interface contracts; start with recorded fixtures, not live hardware.
2. Define operator authorization boundaries, tool allow-lists, and emergency-stop responsibility outside the LLM.
3. Add a replayable scenario suite with sensor anomalies, delayed data and conflicting evidence.
4. Establish a signed or externally anchored audit strategy if higher-assurance provenance is required.
5. Require a separate safety assessment, approvals and controlled environment before any hardware-in-the-loop or real-device work.

All device actuation remains **out of scope** for this prototype.
