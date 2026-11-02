"""Measured local acceptance of three advisory LLM roles.

This runner uses the real Ollama generator only when executed locally.
It reports each role separately and never grants model-based safety authority.
"""

import argparse
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from statistics import mean, median
from time import monotonic
from typing import cast

from ares.evaluation.bounded_team import evaluate_team
from ares.evaluation.independent_review import independent_mean_review
from ares.evaluation.ollama_capability_boundary import Generate, ollama_generator


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    readings: tuple[str, str, str]
    expected_mean: str
    expected_severity: str


CASES = (
    Case("normal_integers", ("16", "18", "20"), "18", "normal"),
    Case("normal_fraction", ("20.5", "21.5", "22.5"), "21.5", "normal"),
    Case("negative", ("-8", "-4", "0"), "-4", "normal"),
    Case("normal_boundary", ("59.8", "59.9", "60"), "59.9", "normal"),
    Case("warning_boundary", ("59", "60", "61"), "60", "warning"),
    Case("warning_decimal", ("61.5", "62.5", "63.5"), "62.5", "warning"),
    Case("warning_upper", ("78", "79", "80"), "79", "warning"),
    Case("critical_boundary", ("79", "80", "81"), "80", "critical"),
    Case("critical_decimal", ("82.5", "83.5", "84.5"), "83.5", "critical"),
)


def _role(prompt: str) -> str:
    if prompt.startswith("Extract the Celsius reading"):
        return "extractor"
    if prompt.startswith("Compute the arithmetic mean"):
        return "arithmetic"
    if prompt.startswith("Independently calculate"):
        return "independent_reviewer"
    return "unknown"


def _grade(raw: str, expected: str) -> bool:
    try:
        actual_number = Decimal(raw.strip())
        expected_number = Decimal(expected)
    except Exception:
        return False
    return actual_number.is_finite() and actual_number == expected_number


def run_suite(
    generate: Generate,
    *,
    repeats: int = 2,
    cases: Sequence[Case] = CASES,
) -> dict[str, object]:
    """Evaluate a fixed, read-only small-task suite without granting autonomy."""
    if not 1 <= repeats <= 5:
        raise ValueError("repeats must be 1..5")
    if not cases or len(cases) > 30:
        raise ValueError("cases must contain 1..30 entries")
    if len({case.name for case in cases}) != len(cases):
        raise ValueError("case names must be unique")
    role_results: dict[str, dict[str, object]] = {
        role: {"attempted": 0, "correct": 0, "errors": 0, "latencies_ms": []}
        for role in ("extractor", "arithmetic", "independent_reviewer")
    }
    results: list[dict[str, object]] = []
    started = monotonic()
    for case in cases:
        for repeat in range(repeats):
            calls: list[tuple[str, str, float, bool]] = []

            def measured(prompt: str) -> str:
                role = _role(prompt)
                stamp = monotonic()
                try:
                    response = generate(prompt)
                except Exception:
                    elapsed = (monotonic() - stamp) * 1000
                    calls.append((role, "", elapsed, True))
                    raise
                calls.append((role, response, (monotonic() - stamp) * 1000, False))
                return response

            readings = tuple(f"{v} C" for v in case.readings)
            outcome = evaluate_team(readings, measured)
            independent_answer = ""
            independent_passed = False
            if outcome.status == "verified" and outcome.verified_mean is not None:
                independent_answer, independent_passed = independent_mean_review(
                    readings, outcome.verified_mean, measured
                )
            expected_mean = Decimal(case.expected_mean)
            case_passed = (
                outcome.status == "verified"
                and outcome.severity == case.expected_severity
                and outcome.verified_mean is not None
                and Decimal(outcome.verified_mean) == expected_mean
                and independent_passed
            )
            for role, answer, elapsed, error in calls:
                if role not in role_results:
                    continue
                item = role_results[role]
                item["attempted"] = cast("int", item["attempted"]) + 1
                if error:
                    item["errors"] = cast("int", item["errors"]) + 1
                latencies = cast("list[float]", item["latencies_ms"])
                latencies.append(elapsed)
                if role == "extractor":
                    index = sum(existing_role == "extractor" for existing_role, *_ in calls[
                        :calls.index((role, answer, elapsed, error))
                    ])
                    expected = case.readings[index]
                else:
                    expected = case.expected_mean
                if not error and _grade(answer, expected):
                    item["correct"] = cast("int", item["correct"]) + 1
            results.append(
                {
                    "case": case.name,
                    "repeat": repeat + 1,
                    "verified": case_passed,
                    "pipeline_status": outcome.status,
                    "pipeline_errors": list(outcome.errors),
                    "expected_severity": case.expected_severity,
                    "actual_severity": outcome.severity,
                    "independent_review_passed": independent_passed,
                    "independent_review_answer": independent_answer,
                }
            )
    role_summary: dict[str, dict[str, object]] = {}
    for role, item in role_results.items():
        attempted = cast("int", item["attempted"])
        correct = cast("int", item["correct"])
        latencies = cast("list[float]", item["latencies_ms"])
        role_summary[role] = {
            "attempted": attempted,
            "correct": correct,
            "accuracy": round(correct / attempted, 4) if attempted else None,
            "errors": item["errors"],
            "latency_mean_ms": round(mean(latencies), 2) if latencies else None,
            "latency_median_ms": round(median(latencies), 2) if latencies else None,
            "latency_max_ms": round(max(latencies), 2) if latencies else None,
        }
    passed = sum(item["verified"] is True for item in results)
    return {
        "scope": "live_raw_ollama",
        "execution_mode": "sequential",
        "cases": len(cases),
        "repeats": repeats,
        "total_scenarios": len(results),
        "passed_scenarios": passed,
        "scenario_accuracy": round(passed / len(results), 4),
        "failed_scenarios": len(results) - passed,
        "wall_time_ms": round((monotonic() - started) * 1000, 2),
        "roles": role_summary,
        "results": results,
        "device_actions": "disabled",
        "safety_authority": "deterministic_python",
        "note": (
            "A bounded fixed-task test, not a claim of general model reliability. "
            "The model never approves risk classifications or device actions."
        ),
    }


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARES consolidated real Ollama acceptance")
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("ares-local-acceptance.json"))
    args = parser.parse_args(argv)
    report = run_suite(ollama_generator(args.model), repeats=args.repeats)
    text = json.dumps(report, indent=2)
    args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["failed_scenarios"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())
