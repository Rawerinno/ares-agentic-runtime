"""Command-line demonstration of ARES diagnostics with optional local Ollama."""

import argparse
import json
from collections.abc import Sequence

from ares.integrations import ReadOnlyToolGateway
from ares.intelligence.diagnostics import build_diagnostic_report
from ares.intelligence.hypotheses import suggested_checks
from ares.intelligence.local import LocalReferenceModel
from ares.intelligence.ollama import OllamaAdapter
from ares.intelligence.ollama_transport import OllamaLocalTransport
from ares.intelligence.resilience import BoundedProposalEngine
from ares.intelligence.transport import ProviderClient, RequestLimits
from ares.safety import Capability, Policy
from ares.simulation import DeviceSimulator
from ares.supervisor import Supervisor


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARES simulated temperature diagnosis")
    parser.add_argument("--temperature", type=float, default=85.0)
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--live", action="store_true", help="Call local Ollama on loopback")
    args = parser.parse_args(argv)

    gateway = ReadOnlyToolGateway(
        Policy(frozenset({("supervisor", "sensor.temperature", Capability.READ)}))
    )
    gateway.register_sensor(
        "sensor.temperature",
        DeviceSimulator("simulated-sensor", initial_temperature_c=args.temperature),
    )
    assessment = Supervisor(gateway).assess(agent_id="supervisor", tool_id="sensor.temperature")
    if args.live:
        limits = RequestLimits(timeout_seconds=30.0, max_response_bytes=16384)
        model = OllamaAdapter(
            ProviderClient(OllamaLocalTransport(), limits),
            args.model,
        )
    else:
        model = LocalReferenceModel()
    result = BoundedProposalEngine(model).evaluate(assessment)
    report = build_diagnostic_report(assessment, result.decision)
    print(
        json.dumps(
            {
                "mode": "ollama" if args.live else "offline-reference",
                "severity": assessment.severity.value,
                "status": result.status.value,
                "proposal": result.decision.kind.value if result.decision else None,
                "error_code": result.error_code,
                "governed_proposal": report.recommendation.value,
                "trusted_explanation": report.explanation,
                "model_consistent": report.model_consistent,
                "model_suggestion": report.model_suggestion,
                "evidence": [
                    {"source": item.source.value, "fact": item.fact} for item in report.evidence
                ],
                "limitations": report.limitation,
                "hypotheses": [
                    {"title": h.title, "verification": h.verification, "status": h.status.value}
                    for h in suggested_checks(assessment)
                ],
            },
            sort_keys=True,
        )
    )
    return 0 if result.decision is not None else 1


if __name__ == "__main__":
    raise SystemExit(run())
