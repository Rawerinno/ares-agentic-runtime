"""Compare two bounded ARES three-agent acceptance reports without invoking models.

This is an evaluation helper, not an authority grant or a statistically powered
claim of model improvement. Reports are local and untrusted until validated.
"""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import cast

_ALLOWED_HYPOTHESES = frozenset({"stable", "thermal_load", "sensor_fault"})


def _read_report(path: Path) -> dict[str, object]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("report must be a JSON object")
    return cast("dict[str, object]", payload)


def _validated_rows(report: dict[str, object]) -> dict[tuple[str, int], dict[str, object]]:
    if report.get("scope") != "governed_three_roles":
        raise ValueError("unsupported report scope")
    if report.get("device_actions") != "disabled":
        raise ValueError("device actions must be disabled")
    if report.get("safety_authority") != "deterministic_supervisor":
        raise ValueError("invalid safety authority")
    rows = report.get("results")
    if not isinstance(rows, list) or not rows or len(rows) > 150:
        raise ValueError("expected 1..150 result rows")
    result: dict[tuple[str, int], dict[str, object]] = {}
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError("invalid result row")
        row = cast("dict[str, object]", item)
        scenario = row.get("scenario")
        repetition = row.get("repeat")
        if (
            not isinstance(scenario, str)
            or not scenario
            or len(scenario) > 100
            or type(repetition) is not int
            or not 1 <= cast("int", repetition) <= 5
            or type(row.get("governed_safe")) is not bool
            or type(row.get("team_accepted")) is not bool
            or row.get("expected_hypothesis") not in _ALLOWED_HYPOTHESES
            or row.get("severity") not in ("normal", "warning", "critical")
        ):
            raise ValueError("invalid result fields")
        key = (scenario, cast("int", repetition))
        if key in result:
            raise ValueError("duplicate scenario/repetition")
        result[key] = row
    if type(report.get("total_runs")) is not int or report["total_runs"] != len(result):
        raise ValueError("invalid total_runs")
    if (
        type(report.get("governed_correct")) is not int
        or report["governed_correct"]
        != sum(row["governed_safe"] is True for row in result.values())
    ):
        raise ValueError("invalid governed_correct")
    if (
        type(report.get("full_team_accepted")) is not int
        or report["full_team_accepted"]
        != sum(row["team_accepted"] is True for row in result.values())
    ):
        raise ValueError("invalid full_team_accepted")
    return result


def compare_reports(
    baseline: dict[str, object], candidate: dict[str, object]
) -> dict[str, object]:
    """Return paired, descriptive comparison; never modify either report."""
    before = _validated_rows(baseline)
    after = _validated_rows(candidate)
    if set(before) != set(after):
        raise ValueError("reports must contain identical scenario/repetition keys")
    if baseline.get("role_contract") != candidate.get("role_contract"):
        raise ValueError("reports use different role contracts")
    if baseline.get("model_source") != candidate.get("model_source"):
        raise ValueError("reports use different model sources")
    for key in before:
        if (
            before[key]["expected_hypothesis"] != after[key]["expected_hypothesis"]
            or before[key]["severity"] != after[key]["severity"]
        ):
            raise ValueError("scenario definitions differ")
    keys = sorted(before)
    gained = [
        f"{s}#{i}"
        for s, i in keys
        if not before[s, i]["team_accepted"] and after[s, i]["team_accepted"]
    ]
    lost = [
        f"{s}#{i}"
        for s, i in keys
        if before[s, i]["team_accepted"] and not after[s, i]["team_accepted"]
    ]
    before_accepted = sum(before[key]["team_accepted"] is True for key in keys)
    after_accepted = sum(after[key]["team_accepted"] is True for key in keys)
    before_safe = sum(before[key]["governed_safe"] is True for key in keys)
    after_safe = sum(after[key]["governed_safe"] is True for key in keys)
    safety_regression = after_safe < before_safe or after_safe != len(keys)
    quality_regression = after_accepted < before_accepted
    return {
        "scope": "paired_three_agent_comparison",
        "model_source": baseline.get("model_source"),
        "role_contract": baseline.get("role_contract"),
        "paired_runs": len(keys),
        "baseline_team_accepted": before_accepted,
        "candidate_team_accepted": after_accepted,
        "team_delta": after_accepted - before_accepted,
        "baseline_governed_correct": before_safe,
        "candidate_governed_correct": after_safe,
        "gained": gained,
        "lost": lost,
        "safety_regression": safety_regression,
        "quality_regression": quality_regression,
        "recommendation": (
            "reject_safety_regression"
            if safety_regression
            else "reject_quality_regression"
            if quality_regression
            else "insufficient_evidence_for_general_reliability"
        ),
        "limitations": (
            "Paired descriptive small-sample comparison; model responses can vary "
            "between repeated runs. No statistical significance, physical safety, "
            "or general model reliability claim."
        ),
    }


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare ARES local acceptance reports")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = compare_reports(_read_report(args.baseline), _read_report(args.candidate))
    except (OSError, ValueError, UnicodeError) as exc:
        parser.exit(2, f"invalid comparison: {type(exc).__name__}\n")
    serialized = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 1 if result["safety_regression"] or result["quality_regression"] else 0


if __name__ == "__main__":
    raise SystemExit(run())
