"""Read-only sensor interpretation with deterministic arithmetic authority.

LLM extraction is verified against bounded unambiguous numeric input.
LLM arithmetic is optional diagnostics only, never a safety dependency.
"""

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from statistics import mean
from time import monotonic

from ares.evaluation.bounded_team import _number, _severity
from ares.evaluation.ollama_capability_boundary import Generate, ollama_generator


@dataclass(frozen=True, slots=True)
class ObservationResult:
    status: str
    extracted: tuple[str, ...]
    verified_mean: str | None
    severity: str | None
    advisory_mean: str | None
    advisory_correct: bool | None
    error_codes: tuple[str, ...]


def observe(
    readings: Sequence[str],
    generate: Generate,
    *,
    evaluate_arithmetic: bool = False,
) -> ObservationResult:
    """Fail closed on incorrect extraction; never trust the model for arithmetic."""
    if len(readings) != 3:
        raise ValueError("exactly three readings are required")
    expected: list[Decimal] = []
    for raw in readings:
        if len(raw) > 100 or not raw.endswith(" C"):
            raise ValueError("expected short Celsius readings")
        tokens = raw.removesuffix(" C").split()
        if len(tokens) != 1:
            raise ValueError("ambiguous Celsius reading")
        value = _number(tokens[0])
        if value is None:
            raise ValueError("invalid or unbounded Celsius value")
        expected.append(value)

    extracted: list[str] = []
    for raw in readings:
        try:
            answer = generate(
                f"Extract the Celsius reading from: 'sensor: {raw}'. Return only the number."
            )
        except Exception:
            answer = ""
        extracted.append(answer)

    if any(_number(answer) != value for answer, value in zip(extracted, expected, strict=True)):
        return ObservationResult(
            "rejected", tuple(extracted), None, None, None, None,
            ("extractor_mismatch",),
        )

    verified = sum(expected, Decimal(0)) / Decimal(3)
    # Python controls the mean and safety category even if the model disagrees.
    advisory: str | None = None
    advisory_correct: bool | None = None
    errors: tuple[str, ...] = ()
    if evaluate_arithmetic:
        try:
            advisory = generate(
                "Compute the arithmetic mean of these Celsius readings: "
                f"{', '.join(extracted)}. Return only the number."
            )
        except Exception:
            advisory = ""
        advisory_correct = _number(advisory) == verified
        if not advisory_correct:
            errors = ("advisory_arithmetic_mismatch",)

    return ObservationResult(
        "verified", tuple(extracted), str(verified), _severity(verified),
        advisory, advisory_correct, errors,
    )


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARES verified local observation")
    parser.add_argument("readings", nargs=3, help="Three simple Celsius readings")
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument(
        "--evaluate-arithmetic",
        action="store_true",
        help="Log LLM calculation as non-authoritative diagnostic",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    readings = tuple(f"{value} C" for value in args.readings)
    model = ollama_generator(args.model)
    latencies: list[float] = []

    def measured(prompt: str) -> str:
        start = monotonic()
        try:
            return model(prompt)
        finally:
            latencies.append((monotonic() - start) * 1000)

    started = monotonic()
    report = observe(readings, measured, evaluate_arithmetic=args.evaluate_arithmetic)
    payload = {
        **asdict(report),
        "authority": "deterministic_python",
        "model_authority": "verified_extraction_only",
        "device_actions": "disabled",
        "metrics": {
            "model_calls": len(latencies),
            "mean_latency_ms": round(mean(latencies), 2) if latencies else None,
            "wall_time_ms": round((monotonic() - started) * 1000, 2),
        },
    }
    output = json.dumps(payload, indent=2)
    if args.output is not None:
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if report.status == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(run())
