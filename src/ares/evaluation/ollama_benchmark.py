"""Compare local Ollama decisions across repeatable simulated sensor cases."""

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass

from ares.integrations import ReadOnlyToolGateway
from ares.intelligence.local import LocalReferenceModel
from ares.intelligence.ollama import OllamaAdapter
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


SCENARIOS = (
    Scenario(20.0, Severity.NORMAL),
    Scenario(59.9, Severity.NORMAL),
    Scenario(60.0, Severity.WARNING),
    Scenario(79.9, Severity.WARNING),
    Scenario(80.0, Severity.CRITICAL),
    Scenario(95.0, Severity.CRITICAL),
)


def benchmark(*, live: bool = False, model: str = "llama3.2:3b") -> dict[str, object]:
    """Run fixed, independent observations, recording each proposal outcome."""
    if live:
        limits = RequestLimits(timeout_seconds=30, max_response_bytes=16384)
        adapter = OllamaAdapter(ProviderClient(OllamaLocalTransport(), limits), model)
    else:
        adapter = LocalReferenceModel()
    engine = BoundedProposalEngine(adapter)
    cases: list[dict[str, object]] = []
    valid = 0
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
        )
        valid += int(passed)
        cases.append(
            {
                "temperature_c": scenario.temperature_c,
                "severity": assessment.severity.value,
                "status": outcome.status.value,
                "proposal": outcome.decision.kind.value if outcome.decision else None,
                "error_code": outcome.error_code,
                "elapsed_ms": round(outcome.elapsed_ms, 2),
                "passed": passed,
            }
        )
    return {
        "mode": "ollama" if live else "offline-reference",
        "model": model if live else None,
        "passed": valid,
        "total": len(SCENARIOS),
        "cases": cases,
    }


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARES model proposal evaluation")
    parser.add_argument("--live", action="store_true", help="Query local Ollama")
    parser.add_argument("--model", default="llama3.2:3b")
    args = parser.parse_args(argv)
    report = benchmark(live=args.live, model=args.model)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(run())
