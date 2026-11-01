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
only if raw answer accuracy is at least 90% **and** every case gives semantically
equivalent answers across repetitions. Numerical answers are compared using exact
finite decimal values, so `20` and `20.0` are equivalent; prose, non-numeric
answers, `NaN` and infinity receive no credit. A failing tier stops the run immediately.
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

## Interpretation of first local run

The initial local Llama 3.2:3B report yielded 9/9 on extraction and marked
6/9 for arithmetic because the evaluator compared `20.0` to `20` as
strings. All nine arithmetic answers were numerically correct. The scorer now
handles such representation differences, and the run should be repeated so
the threshold-classification tier can be measured. This is not evidence for
unseen tasks or general arithmetic reliability.

## Second local run: actual measured limit

Llama 3.2:3B completed all three extraction tasks (9/9) and all three
arithmetic means (9/9) over three repeats each. It classified 59.9 C
correctly but labelled both 60 C and 80 C as "normal" (3/9 correct).
Each answer was repeated consistently, demonstrating that consistency
without correctness is inadequate. **Tier 2 is the observed boundary
for these fixed prompts**; the result does not prove general arithmetic
or sensor-text extraction ability.

Classification, escalation and actuator permissions must always use
trusted deterministic code. The local model must not be asked to
approve or override those decisions.

### Experimental bounded three-role demo

The demo uses a model-backed extractor, a model-backed arithmetic stage,
and an independent deterministic reviewer. It does not use three
independent LLM instances; the roles execute sequentially by design
and the reviewer performs exact validation of the model answers.

On the machine running Ollama:

```powershell
uv run python -m ares.evaluation.bounded_team 55 60 65 --model llama3.2:3b
uv run python -m ares.evaluation.bounded_team 80 85 90 --model llama3.2:3b
```

All inputs must be short finite numeric values. The reviewer computes
the mean and applies safety thresholds using Python, irrespective of
the LLM output. On disagreement or model unavailability, the demo
returns a rejected result, exits with a nonzero status, and never makes
a hardware change. This is a research prototype only; do not connect
it to physical equipment. It is **not** evidence of successful
multi-model orchestration or parallel execution.

The next step is independent unseen-task testing and concurrency
profiling on the user's laptop. We will not broaden the AI's authority
unless those tests justify it.
