"""Compare local Ollama decisions across repeatable simulated sensor cases."""

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import mean, median
from typing import cast

from ares.integrations import ReadOnlyToolGateway
from ares.intelligence.degraded import govern_outcome
from ares.intelligence.local import LocalReferenceModel
from ares.intelligence.ollama import OllamaAdapter
from ares.intelligence.ollama_preemptive import PreemptiveOllamaTransport
from ares.intelligence.ollama_transport import OllamaLocalTransport
from ares.intelligence.resilience import BoundedProposalEngine, OutcomeStatus
from ares.intelligence.transport import ProviderClient, RequestLimits
from ares.safety import Capability, Policy
from ares.simulation import DeviceSimulator
from ares.supervisor import Severity, Supervisor


@dataclass(frozen=True, slots=True)
class Scenario:
    temperature_c: float
    expected: Severity
    expected_kind: str


SCENARIOS = (
    Scenario(20.0, Severity.NORMAL, "observe"),
    Scenario(59.9, Severity.NORMAL, "observe"),
    Scenario(60.0, Severity.WARNING, "investigate"),
    Scenario(79.9, Severity.WARNING, "investigate"),
    Scenario(80.0, Severity.CRITICAL, "request_review"),
    Scenario(95.0, Severity.CRITICAL, "request_review"),
)


def benchmark(
    *, live: bool = False, model: str = "llama3.2:3b", repeats: int = 1, preemptive: bool = False
) -> dict[str, object]:
    """Run fixed, independent observations, recording each proposal outcome."""
    if not 1 <= repeats <= 20:
        raise ValueError("repeats must be between 1 and 20")
    if live:
        limits = RequestLimits(timeout_seconds=30, max_response_bytes=16384)
        adapter = OllamaAdapter(ProviderClient(PreemptiveOllamaTransport() if preemptive else OllamaLocalTransport(), limits), model)
    else:
        adapter = LocalReferenceModel()
    engine = BoundedProposalEngine(adapter)
    cases: list[dict[str, object]] = []
    valid = 0
    governed_valid = 0
    for repeat in range(repeats):
        for scenario in SCENARIOS:
            gateway = ReadOnlyToolGateway(
                Policy(frozenset({("supervisor", "temperature", Capability.READ)}))
            )
            gateway.register_sensor(
                "temperature",
                DeviceSimulator("simulated-sensor", initial_temperature_c=scenario.temperature_c),
            )
            assessment = Supervisor(gateway).assess(agent_id="supervisor", tool_id="temperature")
            outcome = engine.evaluate(assessment)
            passed = (
                assessment.severity is scenario.expected
                and outcome.status is OutcomeStatus.ACCEPTED
                and outcome.decision is not None
                and outcome.decision.kind.value == scenario.expected_kind
            )
            valid += int(passed)
            governed = govern_outcome(assessment, outcome)
            governed_passed = governed.kind.value == scenario.expected_kind
            governed_valid += int(governed_passed)
            cases.append(
                {
                    "temperature_c": scenario.temperature_c,
                    "repeat": repeat + 1,
                    "severity": assessment.severity.value,
                    "status": outcome.status.value,
                    "proposal": outcome.decision.kind.value if outcome.decision else None,
                    "expected_proposal": scenario.expected_kind,
                    "governed_proposal": governed.kind.value,
                    "governance_mode": governed.mode,
                    "governed_passed": governed_passed,
                    "error_code": outcome.error_code,
                    "elapsed_ms": round(outcome.elapsed_ms, 2),
                    "passed": passed,
                }
            )
    durations = [cast("float", item["elapsed_ms"]) for item in cases]
    return {
        "repeats": repeats,
        "latency_mean_ms": round(mean(durations), 2),
        "latency_median_ms": round(median(durations), 2),
        "model_error_count": sum(item["status"] == "model_error" for item in cases),
        "rejected_count": sum(item["status"] == "rejected" for item in cases),
        "evaluation_note": "Raw model and governed scores are distinct; not a safety certification",
        "mode": "ollama" if live else "offline-reference",
        "model": model if live else None,
        "passed": valid,
        "governed_passed": governed_valid,
        "total": len(SCENARIOS) * repeats,
        "cases": cases,
    }


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARES model proposal evaluation")
    parser.add_argument("--live", action="store_true", help="Query local Ollama")
    parser.add_argument("--preemptive", action="store_true", help="Use subprocess timeout")
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--repeats", type=int, default=1, help="Cycles per scenario (1-20)")
    args = parser.parse_args(argv)
    report = benchmark(live=args.live, model=args.model, repeats=args.repeats, preemptive=args.preemptive)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(run())
