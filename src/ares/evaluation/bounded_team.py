"""Read-only three-role ARES demonstration bounded by local-model evaluations.

Roles: LLM extraction -> LLM arithmetic -> deterministic independent reviewer.
The reviewer never accepts a model's safety classification or tool action.
"""

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from statistics import mean
from time import monotonic
from typing import cast

from ares.evaluation.ollama_capability_boundary import Generate, ollama_generator


@dataclass(frozen=True, slots=True)
class BoundedTeamResult:
    status: str
    extracted: tuple[str, ...]
    model_mean: str | None
    verified_mean: str | None
    severity: str | None
    errors: tuple[str, ...]


def _number(value: str) -> Decimal | None:
    if len(value) > 100:
        return None
    try:
        parsed = Decimal(value.strip())
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def _severity(value: Decimal) -> str:
    if value >= Decimal("80"):
        return "critical"
    if value >= Decimal("60"):
        return "warning"
    return "normal"


def evaluate_team(readings: Sequence[str], generate: Generate) -> BoundedTeamResult:
    """Validate AI-proposed values against independent deterministic evidence.

    Caller supplies three short, human-readable temperature readings. The
    deterministic extractor checks a strict numeric format before querying
    the model, so ambiguous inputs cannot be silently trusted.
    """
    if len(readings) != 3:
        raise ValueError("exactly three readings are required")
    expected: list[Decimal] = []
    for item in readings:
        if len(item) > 100 or not item.endswith(" C"):
            raise ValueError("readings must end with ' C' and be at most 100 characters")
        tokens = item.removesuffix(" C").split()
        if len(tokens) != 1:
            raise ValueError("readings must contain a single unambiguous number")
        value = _number(tokens[0])
        if value is None:
            raise ValueError("reading must be a finite numeric value")
        expected.append(value)

    extracted: list[str] = []
    for source, target in zip(readings, expected, strict=True):
        try:
            proposed = generate(
                f"Extract the Celsius reading from: 'sensor: {source}'. Return only the number."
            )
        except Exception:
            proposed = ""
        extracted.append(proposed)
        if _number(proposed) != target:
            return BoundedTeamResult(
                "rejected", tuple(extracted), None, None, None, ("extractor_mismatch",)
            )

    prompt_values = ", ".join(extracted)
    try:
        model_mean = generate(
            "Compute the arithmetic mean of these Celsius readings: "
            f"{prompt_values}. Return only the number."
        )
    except Exception:
        model_mean = ""
    checked_mean = sum(expected, Decimal(0)) / Decimal(3)
    if _number(model_mean) != checked_mean:
        return BoundedTeamResult(
            "rejected",
            tuple(extracted),
            model_mean,
            str(checked_mean),
            None,
            ("arithmetic_mismatch",),
        )
    return BoundedTeamResult(
        "verified",
        tuple(extracted),
        model_mean,
        str(checked_mean),
        _severity(checked_mean),
        (),
    )


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded local 3-role read-only demo")
    parser.add_argument("readings", nargs=3, help="Three numeric Celsius readings")
    parser.add_argument("--model", default="llama3.2:3b")
    args = parser.parse_args(argv)
    readings = tuple(f"{value} C" for value in cast("list[str]", args.readings))
    generate = ollama_generator(args.model)
    latencies_ms: list[float] = []

    def timed_generate(question: str) -> str:
        started = monotonic()
        try:
            return generate(question)
        finally:
            latencies_ms.append((monotonic() - started) * 1000)

    started = monotonic()
    report = evaluate_team(readings, timed_generate)
    wall_time_ms = (monotonic() - started) * 1000
    extraction_attempts = len(report.extracted)
    extraction_successes = extraction_attempts - int("extractor_mismatch" in report.errors)
    arithmetic_attempts = int(report.model_mean is not None)
    arithmetic_successes = int(report.status == "verified")
    attempted = extraction_attempts + arithmetic_attempts
    passed = extraction_successes + arithmetic_successes
    statistics = {
        "model_calls": len(latencies_ms),
        "extraction_correct": extraction_successes,
        "extraction_total": extraction_attempts,
        "arithmetic_correct": arithmetic_successes,
        "arithmetic_total": arithmetic_attempts,
        "model_steps_correct": passed,
        "model_steps_total": attempted,
        "model_steps_accuracy": round(passed / attempted, 4) if attempted else 0.0,
        "latency_mean_ms": round(mean(latencies_ms), 2) if latencies_ms else None,
        "latency_max_ms": round(max(latencies_ms), 2) if latencies_ms else None,
        "wall_time_ms": round(wall_time_ms, 2),
        "execution_mode": "sequential",
    }
    print(
        json.dumps(
            {
                "status": report.status,
                "extracted": report.extracted,
                "model_mean": report.model_mean,
                "verified_mean": report.verified_mean,
                "severity": report.severity,
                "errors": report.errors,
                "authority": "deterministic_reviewer",
                "device_actions": "disabled",
                "statistics": statistics,
            },
            indent=2,
        )
    )
    return 0 if report.status == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(run())
