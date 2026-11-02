"""Conservative scheduling decisions from repeatable, local read-only benchmarks.

The offline policy never invokes Ollama, hardware, GitHub, or external services.
A speed advantage alone cannot override missing accuracy evidence.
"""

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import cast


@dataclass(frozen=True, slots=True)
class SchedulingDecision:
    parallelism: int
    authorized: bool
    reason: str
    accepted_trials: int
    required_trials: int
    median_speedup: float | None
    min_speedup: float | None


def _mode_valid(raw: object) -> bool:
    """Require positive sample count, perfect accuracy, and zero errors."""
    if not isinstance(raw, dict):
        return False
    fields = cast("dict[str, object]", raw)
    total = fields.get("total")
    correct = fields.get("correct")
    accuracy = fields.get("accuracy")
    errors = fields.get("error_count")
    return (
        type(total) is int
        and total > 0
        and type(correct) is int
        and correct == total
        and type(accuracy) in (float, int)
        and accuracy == 1.0
        and type(errors) is int
        and errors == 0
    )


def _read_sample(raw: Mapping[str, object], candidate: int) -> tuple[float, int] | None:
    if raw.get("model_scope") != "raw_model_only":
        return None
    parallelism = raw.get("parallelism")
    sequential = raw.get("sequential")
    concurrent = raw.get("parallel")
    if type(parallelism) is not int or parallelism != candidate:
        return None
    if not _mode_valid(sequential) or not _mode_valid(concurrent):
        return None
    seq = cast("dict[str, object]", sequential)
    par = cast("dict[str, object]", concurrent)
    if seq["total"] != par["total"]:
        return None
    for key in ("wall_time_ms",):
        if type(seq.get(key)) not in (int, float):
            return None
        if type(par.get(key)) not in (int, float):
            return None
    wall_seq = cast("float", seq["wall_time_ms"])
    wall_par = cast("float", par["wall_time_ms"])
    if not 0 < wall_seq < 1e9 or not 0 < wall_par < 1e9:
        return None
    return wall_seq / wall_par, cast("int", seq["total"])


def choose_concurrency(
    reports: Sequence[Mapping[str, object]],
    *,
    candidate: int,
    min_trials: int = 3,
    min_speedup: float = 1.15,
) -> SchedulingDecision:
    """Fail closed without enough accurate, independently collected trials.

    Each report must contain sequential and parallel results for the same
    number of tasks. Do not count a failed or malformed trial as evidence of
    reliable parallel performance.
    """
    if not 2 <= candidate <= 4:
        raise ValueError("candidate parallelism must be between 2 and 4")
    if not 2 <= min_trials <= 20:
        raise ValueError("min_trials must be between 2 and 20")
    if not 1.0 < min_speedup <= 10.0:
        raise ValueError("min_speedup must be in (1, 10]")
    baseline = SchedulingDecision(
        parallelism=1,
        authorized=False,
        reason="insufficient_evidence",
        accepted_trials=0,
        required_trials=min_trials,
        median_speedup=None,
        min_speedup=None,
    )
    if not reports:
        return baseline
    signatures = [json.dumps(report, sort_keys=True) for report in reports]
    if len(set(signatures)) != len(signatures):
        return SchedulingDecision(1, False, "duplicate_trial", 0, min_trials, None, None)
    parsed = [_read_sample(report, candidate) for report in reports]
    valid = [item for item in parsed if item is not None]
    if len(valid) != len(reports):
        return SchedulingDecision(
            1, False, "invalid_or_incorrect_trial", len(valid), min_trials, None, None
        )
    if len(valid) < min_trials:
        return SchedulingDecision(
            1, False, "insufficient_trials", len(valid), min_trials, None, None
        )
    counts = {count for _, count in valid}
    if len(counts) != 1:
        return SchedulingDecision(
            1, False, "incomparable_task_counts", len(valid), min_trials, None, None
        )
    speedups = [speedup for speedup, _ in valid]
    middle = round(median(speedups), 3)
    minimum = round(min(speedups), 3)
    if min(speedups) < min_speedup:
        return SchedulingDecision(
            1, False, "speedup_not_reproducible", len(valid), min_trials, middle, minimum
        )
    return SchedulingDecision(
        candidate, True, "evidence_threshold_met", len(valid), min_trials, middle, minimum
    )


def load_reports(paths: Sequence[Path]) -> list[Mapping[str, object]]:
    """Read bounded local benchmark JSON; never fetch remote data."""
    reports: list[Mapping[str, object]] = []
    for path in paths:
        if path.stat().st_size > 2_000_000:
            raise ValueError("benchmark report is too large")
        result: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(result, dict):
            raise ValueError("benchmark must be a JSON object")
        reports.append(cast("dict[str, object]", result))
    return reports


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline, conservative ARES concurrency policy")
    parser.add_argument("reports", nargs="*", type=Path, help="Local benchmark JSON files")
    parser.add_argument("--candidate", type=int, default=2)
    args = parser.parse_args(argv)
    decision = choose_concurrency(load_reports(args.reports), candidate=args.candidate)
    print(json.dumps(asdict(decision), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
