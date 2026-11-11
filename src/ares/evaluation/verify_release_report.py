"""Independently validate a persisted offline release acceptance report.

This checks report consistency and required invariants; it does not attest that
the producer or the underlying simulated execution is trustworthy.
"""

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> object:
    raise ValueError(f"non-finite JSON constant: {value}")


def validate_report(value: object) -> tuple[str, ...]:
    if not isinstance(value, dict):
        return ("report_not_object",)
    report = cast(Mapping[str, object], value)
    errors: list[str] = []
    expected_fields = {
        "scope",
        "scenario_count",
        "simulated_model_calls",
        "audit_entries_checked",
        "checks",
        "passed",
        "total",
        "all_passed",
        "default_parallelism",
        "device_actions",
        "limitations",
    }
    if set(report) != expected_fields:
        errors.append("report_field_set_mismatch")

    def require(name: str, expected: object) -> None:
        actual = report.get(name)
        if type(actual) is not type(expected) or actual != expected:
            errors.append(f"{name}_invalid")

    require("scope", "offline_stub_only")
    require("scenario_count", 121)
    require("simulated_model_calls", 484)
    require("audit_entries_checked", 121)
    require("default_parallelism", 1)
    require("device_actions", "disabled")
    require("all_passed", True)
    checks = report.get("checks")
    required = {
        "default_sequential",
        "scenario_accuracy",
        "audit_chain",
        "extraction_fail_closed",
        "arithmetic_fail_closed",
        "independent_review_rejects_wrong",
        "independent_review_accepts_correct",
        "provider_failure_fail_closed",
        "extreme_input_rejected",
    }
    if not isinstance(checks, dict) or any(
        not isinstance(k, str) or type(v) is not bool
        for k, v in cast(Mapping[object, object], checks).items()
    ):
        errors.append("checks_invalid")
    else:
        typed_checks = cast(Mapping[object, object], checks)
        if set(typed_checks) != required:
            errors.append("check_set_mismatch")
        validated_checks: dict[str, bool] = {
            key: value
            for key, value in typed_checks.items()
            if isinstance(key, str) and isinstance(value, bool)
        }
        if not all(validated_checks.values()):
            errors.append("checks_failed")
        if report.get("total") != len(validated_checks) or type(report.get("total")) is not int:
            errors.append("total_mismatch")
        passed = report.get("passed")
        if type(passed) is not int or passed != sum(validated_checks.values()):
            errors.append("passed_mismatch")
        if report.get("all_passed") is not all(validated_checks.values()):
            errors.append("all_passed_mismatch")
    limitations = report.get("limitations")
    expected_limitations = (
        "These tests validate deterministic software invariants, not "
        "Ollama generalization, live concurrency performance, or hardware safety."
    )
    if type(limitations) is not str or limitations != expected_limitations:
        errors.append("limitations_invalid")
    return tuple(errors)


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate offline ARES release report")
    parser.add_argument("report", type=Path)
    args = parser.parse_args(argv)
    try:
        data = json.loads(
            args.report.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"release report unreadable: {type(exc).__name__}")
        return 1
    errors = validate_report(data)
    if errors:
        print("release report rejected: " + ", ".join(errors))
        return 1
    print("release report invariants verified (offline simulation only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
