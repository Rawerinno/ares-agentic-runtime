"""Read-only three-role ARES demonstration bounded by local-model evaluations.

Roles: LLM extraction -> LLM arithmetic -> deterministic independent reviewer.
The reviewer never accepts a model's safety classification or tool action.
"""

import argparse
import json
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import mean
from threading import Lock
from time import monotonic
from typing import cast

from ares.evaluation.audit_storage import extend_audit, read_audit
from ares.evaluation.bounded_team_audit import record_bounded_execution
from ares.evaluation.concurrency_policy import choose_concurrency, load_reports
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


def evaluate_team(
    readings: Sequence[str], generate: Generate, *, parallelism: int = 1
) -> BoundedTeamResult:
    """Validate AI-proposed values against independent deterministic evidence.

    Caller supplies three short, human-readable temperature readings. The
    deterministic extractor checks a strict numeric format before querying
    the model, so ambiguous inputs cannot be silently trusted.
    """
    if len(readings) != 3:
        raise ValueError("exactly three readings are required")
    if not 1 <= parallelism <= 3:
        raise ValueError("parallelism must be 1..3")
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

    def extract(source: str) -> str:
        try:
            return generate(
                f"Extract the Celsius reading from: 'sensor: {source}'. Return only the number."
            )
        except Exception:
            return ""

    if parallelism == 1:
        extracted = [extract(source) for source in readings]
    else:
        with ThreadPoolExecutor(max_workers=parallelism) as pool:
            extracted = list(pool.map(extract, readings))
    if any(
        _number(proposed) != target for proposed, target in zip(extracted, expected, strict=True)
    ):
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
    parser.add_argument("--audit-file", type=Path, help="Optional local hash-chained JSONL audit")
    parser.add_argument("--candidate", type=int, default=2, choices=(2, 3))
    parser.add_argument(
        "--benchmark-report",
        type=Path,
        action="append",
        default=[],
        help="Independent raw-model performance reports (3 required to enable concurrency)",
    )
    args = parser.parse_args(argv)
    decision = choose_concurrency(load_reports(args.benchmark_report), candidate=args.candidate)
    readings = tuple(f"{value} C" for value in cast("list[str]", args.readings))
    generate = ollama_generator(args.model)
    latencies_ms: list[float] = []
    latency_lock = Lock()

    def timed_generate(question: str) -> str:
        started = monotonic()
        try:
            return generate(question)
        finally:
            elapsed = (monotonic() - started) * 1000
            with latency_lock:
                latencies_ms.append(elapsed)

    started = monotonic()
    report = evaluate_team(readings, timed_generate, parallelism=decision.parallelism)
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
        "execution_mode": "parallel" if decision.parallelism > 1 else "sequential",
        "parallelism": decision.parallelism,
    }
    audit_digest: str | None = None
    if args.audit_file is not None:
        previous = read_audit(args.audit_file)
        audit = record_bounded_execution(
            previous,
            report,
            decision,
            call_count=len(latencies_ms),
            elapsed_ms=wall_time_ms,
        )
        extend_audit(args.audit_file, previous, audit)
        audit_digest = audit[-1].digest
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
                "scheduling_decision": asdict(decision),
                "audit_digest": audit_digest,
            },
            indent=2,
        )
    )
    return 0 if report.status == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(run())
