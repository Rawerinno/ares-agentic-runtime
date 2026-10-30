"""Consolidated Phase 4 checks."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

from ares.evaluation.audit import append_entry
from ares.evaluation.audit_storage import extend_audit, read_audit
from ares.evaluation.ollama_benchmark import benchmark
from ares.evaluation.phase4_acceptance import phase4_acceptance
from ares.intelligence.decisions import DecisionKind
from ares.intelligence.degraded import govern_outcome
from ares.intelligence.resilience import OutcomeStatus, ProposalOutcome
from ares.simulation import DeviceSnapshot
from ares.supervisor import Assessment, Severity

Report = dict[str, object]


def validate(
    *, live: bool = False, model: str = "llama3.2:3b", repeats: int = 2,
    preemptive: bool = False,
) -> Report:
    gates = phase4_acceptance()
    with TemporaryDirectory() as directory:
        path = Path(directory) / "audit.jsonl"
        first = append_entry((), "sample", {"temperature_c": 20})
        extend_audit(path, (), first)
        second = append_entry(read_audit(path), "sample", {"temperature_c": 85})
        extend_audit(path, first, second)
        audit_verified = read_audit(path) == second
    assessment = Assessment(
        DeviceSnapshot("simulated", 1, 85.0, True),
        Severity.CRITICAL,
        "Critical simulated temperature",
        "Request engineer review",
    )
    error = ProposalOutcome(OutcomeStatus.MODEL_ERROR, None, "model_exception", 1.0)
    fallback = govern_outcome(assessment, error)
    degraded_ok = (
        fallback.mode == "deterministic_degraded"
        and fallback.kind is DecisionKind.REQUEST_REVIEW
        and not fallback.model_accepted
    )
    cases = benchmark(live=live, model=model, repeats=repeats, preemptive=preemptive)
    checks = {
        "offline_acceptance": gates["passed"] == gates["total"],
        "governed_cases": cases["governed_passed"] == cases["total"],
        "model_available": cases["model_error_count"] == 0,
        "no_rejected_responses": cases["rejected_count"] == 0,
        "audit_two_event_roundtrip": audit_verified,
        "mocked_degraded_fallback": degraded_ok,
    }
    return {
        "checks": checks,
        "passed": sum(checks.values()),
        "total": len(checks),
        "scenario_count": cases["total"],
        "governed_correct": cases["governed_passed"],
        "raw_correct": cases["passed"],
        "model_errors": cases["model_error_count"],
        "rejected_responses": cases["rejected_count"],
        "latency_mean_ms": cases["latency_mean_ms"],
        "latency_median_ms": cases["latency_median_ms"],
    }


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--preemptive", action="store_true")
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args(argv)
    result = validate(
        live=args.live, model=args.model, repeats=args.repeats, preemptive=args.preemptive
    )
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] == result["total"] else 1


if __name__ == "__main__":
    raise SystemExit(run())
