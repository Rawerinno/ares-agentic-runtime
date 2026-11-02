"""Read-only benchmark: unseen simple tasks and Ollama concurrency on localhost.

Measures the raw LLM only. Never treats a model answer as a safety decision.
"""

import argparse
import json
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from statistics import mean, median
from time import monotonic
from typing import cast

from ares.evaluation.ollama_capability_boundary import ollama_generator


@dataclass(frozen=True, slots=True)
class WorkItem:
    name: str
    prompt: str
    expected: Decimal


CASES = (
    WorkItem(
        "extract_fraction",
        "Extract Celsius: 'probe is 21.5 C'. Number only.",
        Decimal("21.5"),
    ),
    WorkItem(
        "extract_negative",
        "Extract Celsius: 'probe is -12.25 C'. Number only.",
        Decimal("-12.25"),
    ),
    WorkItem(
        "extract_decimal",
        "Extract Celsius: 'probe is 73.2 C'. Number only.",
        Decimal("73.2"),
    ),
    WorkItem(
        "mean_fraction",
        "Mean of Celsius readings: 10, 11, 12. Number only.",
        Decimal("11"),
    ),
    WorkItem(
        "mean_decimal",
        "Mean of Celsius readings: 20.5, 21.5, 22.5. Number only.",
        Decimal("21.5"),
    ),
    WorkItem(
        "mean_negative",
        "Mean of Celsius readings: -8, -4, 0. Number only.",
        Decimal("-4"),
    ),
)


def correct(answer: str, expected: Decimal) -> bool:
    """Strict exact numeric equality; do not accept prose or NaN/Infinity."""
    if len(answer) > 100:
        return False
    try:
        actual = Decimal(answer.strip())
    except InvalidOperation:
        return False
    return actual.is_finite() and actual == expected


def benchmark(
    generate: Callable[[str], str],
    *,
    parallelism: int = 3,
    repeats: int = 2,
    cases: Sequence[WorkItem] = CASES,
) -> dict[str, object]:
    """Compare same task batch in sequential and concurrent modes.

    Calls are fully independent. Latency and model agreement are measured
    separately; concurrency is never assumed faster.
    """
    if not 1 <= parallelism <= 8:
        raise ValueError("parallelism must be 1..8")
    if not 1 <= repeats <= 10:
        raise ValueError("repeats must be 1..10")
    if not cases:
        raise ValueError("at least one case required")

    scenarios: list[dict[str, object]] = []
    for mode in ("sequential", "parallel"):
        attempts: list[dict[str, object]] = []

        def query(item: WorkItem) -> dict[str, object]:
            started = monotonic()
            try:
                answer = generate(item.prompt)
                error = None
            except Exception:
                answer = ""
                error = "model_error"
            return {
                "name": item.name,
                "answer": answer,
                "expected": str(item.expected),
                "correct": error is None and correct(answer, item.expected),
                "error": error,
                "latency_ms": round((monotonic() - started) * 1000, 2),
            }

        start = monotonic()
        for _ in range(repeats):
            if mode == "sequential":
                attempts.extend(query(item) for item in cases)
            else:
                with ThreadPoolExecutor(max_workers=parallelism) as pool:
                    attempts.extend(pool.map(query, cases))
        wall_ms = (monotonic() - start) * 1000
        count = len(attempts)
        valid = sum(item["correct"] is True for item in attempts)
        latencies = [cast("float", item["latency_ms"]) for item in attempts]
        error_count = sum(item["error"] is not None for item in attempts)
        stable = all(
            len({str(a["answer"]) for a in attempts if a["name"] == case.name}) == 1
            for case in cases
        )
        scenarios.append(
            {
                "mode": mode,
                "correct": valid,
                "total": count,
                "accuracy": round(valid / count, 4),
                "error_count": error_count,
                "consistent_exact_text": stable,
                "latency_mean_ms": round(mean(latencies), 2),
                "latency_median_ms": round(median(latencies), 2),
                "latency_max_ms": round(max(latencies), 2),
                "wall_time_ms": round(wall_ms, 2),
                "attempts": attempts,
            }
        )
    sequential = cast("float", scenarios[0]["wall_time_ms"])
    concurrent = cast("float", scenarios[1]["wall_time_ms"])
    return {
        "model_scope": "raw_model_only",
        "parallelism": parallelism,
        "repeats": repeats,
        "task_count_per_mode": len(cases) * repeats,
        "sequential": scenarios[0],
        "parallel": scenarios[1],
        "speedup": round(sequential / concurrent, 3) if concurrent > 0 else None,
        "parallel_faster": concurrent < sequential,
        "safety_note": "Read-only test; classifications and device actions disabled.",
        "limitations": (
            "Small fixed tasks and execution-order effects prevent general reliability "
            "claims. All model answers must be independently validated."
        ),
    }


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARES local raw-model parallel comparison")
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--parallelism", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--output", default="parallel-report.json")
    args = parser.parse_args(argv)
    generate = ollama_generator(args.model)
    report = benchmark(generate, parallelism=args.parallelism, repeats=args.repeats)
    result = json.dumps(report, indent=2)
    from pathlib import Path

    Path(args.output).write_text(result + "\n", encoding="utf-8")
    print(result)
    seq = report["sequential"]
    par = report["parallel"]
    if not isinstance(seq, dict) or not isinstance(par, dict):
        return 1
    return 0 if seq["accuracy"] == 1.0 and par["accuracy"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(run())
