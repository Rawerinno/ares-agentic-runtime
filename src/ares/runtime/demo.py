"""Local, offline demonstration of the durable incident workflow."""

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from ares.integrations import ReadOnlyToolGateway
from ares.intelligence.decisions import ModelAdapter
from ares.intelligence.local import LocalReferenceModel
from ares.intelligence.ollama import OllamaAdapter
from ares.intelligence.ollama_transport import OllamaLocalTransport
from ares.intelligence.transport import ProviderClient, RequestLimits
from ares.evaluation.ollama_capability_boundary import ollama_generator
from ares.runtime.governed_three_agents import GovernedThreeAgentTeam
from ares.runtime.multi_agent_mvp import SqliteTaskStore, run_incident
from ares.safety import Capability, Policy
from ares.simulation import DeviceSimulator
from ares.supervisor import Supervisor


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARES durable multi-agent simulation MVP")
    parser.add_argument("--temperature", type=float, default=85.0)
    parser.add_argument("--task-id", default="demo-critical")
    parser.add_argument("--db", type=Path, default=Path(".ares-incident-tasks.sqlite3"))
    parser.add_argument("--recover", action="store_true")
    parser.add_argument("--advisor", choices=("none", "offline", "ollama"), default="none")
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--team", choices=("none", "offline", "ollama"), default="none")
    args = parser.parse_args(argv)

    device = DeviceSimulator("demo-sim", initial_temperature_c=args.temperature)
    gateway = ReadOnlyToolGateway(Policy(frozenset({("observer", "sensor", Capability.READ)})))
    gateway.register_sensor("sensor", device)
    if args.team != "none" and args.advisor != "none":
        parser.error("--team and --advisor cannot both be enabled")
    store = SqliteTaskStore(args.db)
    advisor: ModelAdapter | None = None
    if args.advisor == "offline":
        advisor = LocalReferenceModel()
    elif args.advisor == "ollama":
        advisor = OllamaAdapter(
            ProviderClient(
                OllamaLocalTransport(),
                RequestLimits(timeout_seconds=30.0, max_response_bytes=16384),
            ),
            args.model,
        )
    team: GovernedThreeAgentTeam | None = None
    if args.team == "offline":

        def offline_team(question: str) -> str:
            context = question.split("Trusted context: ", 1)[1].removesuffix(".")
            data = json.loads(context)
            severity = data["severity"]
            role = question.split("ROLE=", 1)[1].split(".", 1)[0]
            if role == "investigator":
                hypothesis = (
                    "sensor_fault"
                    if not data["healthy"] or data["temperature_c"] is None
                    else "stable"
                    if severity == "normal"
                    else "thermal_load"
                )
                return json.dumps({"hypothesis": hypothesis, "severity": severity})
            if role == "planner":
                action = {
                    "normal": "monitor",
                    "warning": "inspect",
                    "critical": "human_review",
                }[severity]
                return json.dumps({"plan": action, "severity": severity})
            return json.dumps({"verdict": "consistent", "severity": severity})

        team = GovernedThreeAgentTeam(offline_team, identity="three-offline-v1")
    elif args.team == "ollama":
        team = GovernedThreeAgentTeam(
            ollama_generator(args.model), identity=f"three-ollama-v1:{args.model}"
        )
    report = run_incident(
        Supervisor(gateway),
        store,
        task_id=args.task_id,
        agent_id="observer",
        tool_id="sensor",
        recover=args.recover,
        advisor=advisor,
        team=team,
    )
    print(
        json.dumps(
            {
                "report": asdict(report),
                "tasks": store.summary(),
                "execution_scope": "local_simulation_advisory_only",
                "advisor": args.advisor,
                "team": args.team,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
