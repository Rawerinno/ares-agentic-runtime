"""Deterministic offline release acceptance for the bounded ARES prototype.

This does NOT exercise Ollama or estimate real model accuracy. It verifies
the safety boundary, arithmetic reference checks, auditing and fail-closed
behavior using repeatable simulated LLM responses.
"""

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import cast

from ares.evaluation.audit import verify_entries
from ares.evaluation.bounded_team import BoundedTeamResult, evaluate_team
from ares.evaluation.bounded_team_audit import record_bounded_execution
from ares.evaluation.concurrency_policy import choose_concurrency
from ares.evaluation.independent_review import independent_mean_review


def _stub(question: str) -> str:
    if question.startswith("Extract the Celsius reading"):
        return question.split("sensor: ", 1)[1].split(" C", 1)[0]
    if question.startswith("Compute the arithmetic mean"):
        values = question.split("readings: ", 1)[1].rsplit(". Return only the number.", 1)[0]
    elif question.startswith("Independently calculate"):
        values = question.split("measurements: ", 1)[1].rsplit(". Return only the number.", 1)[0]
    else:
        raise ValueError("unrecognized prompt")
    numbers = [Decimal(v.strip()) for v in values.split(",")]
    return str(sum(numbers, Decimal(0)) / Decimal(len(numbers)))


def _severity(value: Decimal) -> str:
    return "critical" if value >= 80 else "warning" if value >= 60 else "normal"


def acceptance_report() -> dict[str, object]:
    """Run 121 representative boundary cases and distinct failure injections."""
    checks: dict[str, bool] = {}
    model_calls = 0
    completed = 0
    audited = ()
    policy = choose_concurrency([], candidate=2)
    checks["default_sequential"] = policy.parallelism == 1 and not policy.authorized

    for center in range(-20, 101):
        triple = (Decimal(center - 1), Decimal(center), Decimal(center + 1))
        readings = tuple(f"{value} C" for value in triple)

        def simulate(question: str) -> str:
            nonlocal model_calls
            model_calls += 1
            return _stub(question)

        result = evaluate_team(readings, simulate)
        if (
            result.status != "verified"
            or result.severity != _severity(triple[1])
            or result.verified_mean != str(triple[1])
        ):
            checks[f"scenario_{center}"] = False
        completed += 1
        audited = record_bounded_execution(
            audited, result, policy, call_count=4, elapsed_ms=1.0
        )
    verify_entries(audited)
    checks["scenario_accuracy"] = completed == 121 and model_calls == 484
    checks["audit_chain"] = len(audited) == completed and audited[-1].sequence == completed

    def bad_extraction(question: str) -> str:
        if question.startswith("Extract"):
            return "999"
        return _stub(question)

    bad = evaluate_team(("55 C", "60 C", "65 C"), bad_extraction)
    checks["extraction_fail_closed"] = (
        bad.status == "rejected" and bad.severity is None
        and bad.errors == ("extractor_mismatch",)
    )

    def bad_arithmetic(question: str) -> str:
        return "999" if question.startswith("Compute") else _stub(question)

    bad = evaluate_team(("55 C", "60 C", "65 C"), bad_arithmetic)
    checks["arithmetic_fail_closed"] = (
        bad.status == "rejected" and bad.severity is None
        and bad.errors == ("arithmetic_mismatch",)
    )
    _, agreed = independent_mean_review(("55 C", "60 C", "65 C"), "60", lambda _: "61")
    checks["independent_review_rejects_wrong"] = not agreed
    _, agreed = independent_mean_review(("55 C", "60 C", "65 C"), "60", _stub)
    checks["independent_review_accepts_correct"] = agreed

    def unavailable(_question: str) -> str:
        raise RuntimeError("offline")

    bad = evaluate_team(("55 C", "60 C", "65 C"), unavailable)
    checks["provider_failure_fail_closed"] = bad.status == "rejected" and bad.severity is None
    try:
        evaluate_team(("1e999999999 C", "60 C", "65 C"), _stub)
    except ValueError:
        checks["extreme_input_rejected"] = True
    else:
        checks["extreme_input_rejected"] = False

    return {
        "scope": "offline_stub_only",
        "scenario_count": completed,
        "simulated_model_calls": model_calls,
        "audit_entries_checked": len(audited),
        "checks": checks,
        "passed": sum(checks.values()),
        "total": len(checks),
        "all_passed": all(checks.values()),
        "default_parallelism": policy.parallelism,
        "device_actions": "disabled",
        "limitations": (
            "These tests validate deterministic software invariants, not "
            "Ollama generalization, live concurrency performance, or hardware safety."
        ),
    }


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline ARES release acceptance")
    parser.add_argument("--output", type=Path, help="Optional JSON report destination")
    args = parser.parse_args(argv)
    report = acceptance_report()
    result = json.dumps(report, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.write_text(result + "\n", encoding="utf-8")
    print(result)
    return 0 if report["all_passed"] is True else 1


if __name__ == "__main__":
    raise SystemExit(run())
