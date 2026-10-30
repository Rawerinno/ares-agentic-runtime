"""One command for consolidated offline or local-Ollama validation."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

from ares.evaluation.audit import append_entry
from ares.evaluation.audit_storage import extend_audit, read_audit
from ares.evaluation.ollama_benchmark import benchmark
from ares.evaluation.phase4_acceptance import phase4_acceptance


def validate(*, live: bool = False, model: str = "llama3.2:3b", repeats: int = 2) -> dict[str, object]:
    """Group fixed-scenario inference, offline gates and audit persistence."""
    gates = phase4_acceptance()
    with TemporaryDirectory(prefix="ares-phase4-") as folder:
        path = Path(folder) / "audit.jsonl"
        first = append_entry((), "sample", {"reading": 20})
        extend_audit(path, (), first)
        second = append_entry(read_audit(path), "sample", {"reading": 85})
        extend_audit(path, first, second)
        audit_ok = read_audit(path) == second

    results = benchmark(live=live, model=model, repeats=repeats)
    checks = {
        "offline_acceptance": gates["passed"] == gates["total"],
        "audit_two_events": audit_ok,
        "governed_cases": results["governed_passed"] == results["total"],
        "no_model_errors": results["model_error_count"] == 0,
        "no_rejected_responses": results["rejected_count"] == 0,
    }
    return {
        "phase": 4,
        "mode": "ollama" if live else "offline-reference",
        "checks": checks,
        "passed": sum(checks.values()),
        "total": len(checks),
        "raw_correct": results["passed"],
        "governed_correct": results["governed_passed"],
        "scenario_count": results["total"],
        "latency_mean_ms": results["latency_mean_ms"],
        "latency_median_ms": results["latency_median_ms"],
        "note": "Simulated scenarios, not a safety certification",
    }


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARES consolidated Phase 4 checks")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args(argv)
    result = validate(live=args.live, model=args.model, repeats=args.repeats)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] == result["total"] else 1


if __name__ == "__main__":
    raise SystemExit(run())
