"""Measure raw local Ollama competence before enabling more complex ARES agents.

A failed tier stops the evaluation; governed fallbacks cannot inflate this score.
No hardware tools, file modification, cloud services or autonomous agents are used.
"""

import argparse
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from statistics import mean
from time import monotonic
from typing import cast

from ares.intelligence.ollama_transport import OllamaLocalTransport
from ares.intelligence.transport import RequestLimits


@dataclass(frozen=True, slots=True)
class Probe:
    tier: int
    name: str
    question: str
    expected: str


PROBES = (
    Probe(
        1,
        "extract_20",
        "Extract the Celsius reading from: 'sensor A: 20 C'. Return only the number.",
        "20",
    ),
    Probe(
        1,
        "extract_85",
        "Extract the Celsius reading from: 'sensor B reports 85 degrees C'. "
        "Return only the number.",
        "85",
    ),
    Probe(
        1,
        "extract_negative",
        "Extract the Celsius reading from: 'sensor C: -5 C'. Return only the number.",
        "-5",
    ),
    Probe(
        2,
        "mean_20",
        "Compute the arithmetic mean of these Celsius readings: 18, 20, 22. "
        "Return only the number.",
        "20",
    ),
    Probe(
        2,
        "mean_60",
        "Compute the arithmetic mean of these Celsius readings: 55, 60, 65. "
        "Return only the number.",
        "60",
    ),
    Probe(
        2,
        "mean_85",
        "Compute the arithmetic mean of these Celsius readings: 80, 85, 90. "
        "Return only the number.",
        "85",
    ),
    Probe(
        3,
        "normal_edge",
        "Classify 59.9 C: normal if below 60; warning if 60 to below 80; "
        "critical if 80 or above. Return only the class.",
        "normal",
    ),
    Probe(
        3,
        "warning_edge",
        "Classify 60 C: normal if below 60; warning if 60 to below 80; "
        "critical if 80 or above. Return only the class.",
        "warning",
    ),
    Probe(
        3,
        "critical_edge",
        "Classify 80 C: normal if below 60; warning if 60 to below 80; "
        "critical if 80 or above. Return only the class.",
        "critical",
    ),
)


Generate = Callable[[str], str]


def _normalized_answer(answer: str | None, *, numeric: bool) -> str | None:
    """Compare numeric answers by value, without accepting prose or non-finite values."""
    if answer is None:
        return None
    value = answer.strip()
    if not numeric:
        return value
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    return str(number.normalize()) if number.is_finite() else None


def ollama_generator(model: str, *, timeout: float = 30.0) -> Generate:
    """Return a bounded localhost-only Ollama generator with deterministic sampling."""
    if not model.strip():
        raise ValueError("model must not be empty")
    transport = OllamaLocalTransport()
    limits = RequestLimits(timeout_seconds=timeout, max_response_bytes=8192)

    def generate(question: str) -> str:
        request = {
            "model": model,
            "prompt": (
                "You are being evaluated on a small, self-contained engineering task. "
                "Follow the question exactly. Respond using a JSON object with a single "
                'string field named "answer". No additional fields.\nQuestion: ' + question
            ),
            "stream": False,
            "think": False,
            "format": {
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
                "additionalProperties": False,
            },
            "options": {"temperature": 0, "num_predict": 80},
        }
        raw = transport.request(json.dumps(request).encode("utf-8"), limits=limits)
        envelope: object = json.loads(raw)
        if not isinstance(envelope, dict):
            raise ValueError("invalid envelope")
        response = cast("dict[str, object]", envelope).get("response")
        if not isinstance(response, str):
            raise ValueError("missing response")
        decoded: object = json.loads(response)
        if not isinstance(decoded, dict) or set(cast("dict[str, object]", decoded)) != {"answer"}:
            raise ValueError("invalid answer shape")
        answer = cast("dict[str, object]", decoded)["answer"]
        if not isinstance(answer, str) or len(answer) > 100:
            raise ValueError("invalid answer")
        return answer.strip()

    return generate


def evaluate(
    generate: Generate,
    *,
    repeats: int = 3,
    min_accuracy: float = 0.90,
) -> dict[str, object]:
    """Stop at the first tier failing accuracy or semantic repeatability.

    Numeric answers compare by exact Decimal value; categorical answers compare
    as written. Invalid and missing answers never earn correctness credit.
    """
    if not 2 <= repeats <= 10:
        raise ValueError("repeats must be between 2 and 10")
    if not 0 < min_accuracy <= 1:
        raise ValueError("min_accuracy must be in (0, 1]")
    tiers: list[dict[str, object]] = []
    trusted_tier = 0
    for tier in sorted({case.tier for case in PROBES}):
        rows: list[dict[str, object]] = []
        for case in (probe for probe in PROBES if probe.tier == tier):
            answers: list[str | None] = []
            latencies: list[float] = []
            for _ in range(repeats):
                start = monotonic()
                try:
                    answer = generate(case.question)
                except Exception:
                    answer = None
                latencies.append(round((monotonic() - start) * 1000, 2))
                answers.append(answer)
            numeric = tier in (1, 2)
            normalized = [_normalized_answer(answer, numeric=numeric) for answer in answers]
            expected_normalized = _normalized_answer(case.expected, numeric=numeric)
            rows.append(
                {
                    "case": case.name,
                    "expected": case.expected,
                    "answers": answers,
                    "correct": sum(a is not None and a == expected_normalized for a in normalized),
                    "consistent": len(set(normalized)) == 1,
                    "latency_mean_ms": round(mean(latencies), 2),
                }
            )
        total = len(rows) * repeats
        correct = sum(cast("int", row["correct"]) for row in rows)
        accuracy = correct / total
        all_consistent = all(row["consistent"] is True for row in rows)
        passed = accuracy >= min_accuracy and all_consistent
        tiers.append(
            {
                "tier": tier,
                "accuracy": round(accuracy, 4),
                "correct": correct,
                "total": total,
                "all_consistent": all_consistent,
                "passed": passed,
                "cases": rows,
            }
        )
        if not passed:
            break
        trusted_tier = tier
    return {
        "model_scope": "raw_model_only",
        "repeats": repeats,
        "min_accuracy": min_accuracy,
        "highest_passing_tier": trusted_tier,
        "stopped_at_tier": tiers[-1]["tier"] if not tiers[-1]["passed"] else None,
        "tiers": tiers,
        "limitations": (
            "Passing these fixed probes does not establish general capability or safety; "
            "run additional unseen tests before deployment."
        ),
    }


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARES local Ollama capability boundary")
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--min-accuracy", type=float, default=0.90)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--output", help="Optional JSON result file")
    args = parser.parse_args(argv)
    report = evaluate(
        ollama_generator(args.model, timeout=args.timeout),
        repeats=args.repeats,
        min_accuracy=args.min_accuracy,
    )
    output = json.dumps(report, indent=2)
    if args.output:
        from pathlib import Path

        Path(args.output).write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if report["highest_passing_tier"] == max(case.tier for case in PROBES) else 1


if __name__ == "__main__":
    raise SystemExit(run())
