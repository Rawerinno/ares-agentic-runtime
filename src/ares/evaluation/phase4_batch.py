"""Consolidated Phase 4 checks."""

import argparse
import json
from collections.abc import Sequence
from ares.evaluation.phase4_acceptance import phase4_acceptance
from ares.evaluation.ollama_benchmark import benchmark


Report = dict[str, object]


def validate(*, live: bool = False, model: str = "llama3.2:3b", repeats: int = 2) -> Report:
    gates = phase4_acceptance()
    cases = benchmark(live=live, model=model, repeats=repeats)
    checks = {
        "offline_acceptance": gates["passed"] == gates["total"],
        "governed_cases": cases["governed_passed"] == cases["total"],
        "model_available": cases["model_error_count"] == 0,
    }
    return {
        "checks": checks,
        "passed": sum(checks.values()),
        "total": len(checks),
        "scenario_count": cases["total"],
        "governed_correct": cases["governed_passed"],
        "raw_correct": cases["passed"],
    }


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args(argv)
    result = validate(live=args.live, model=args.model, repeats=args.repeats)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] == result["total"] else 1


if __name__ == "__main__":
    raise SystemExit(run())
