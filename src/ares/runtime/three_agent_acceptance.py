"""Reproducible read-only acceptance of three governed model roles.

Offline uses a deterministic reference; --live uses the local Ollama model.
Safety is measured separately from raw model-role acceptance.
"""

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median
from tempfile import TemporaryDirectory
from time import monotonic

from ares.evaluation.ollama_capability_boundary import Generate, ollama_generator
from ares.integrations import ReadOnlyToolGateway
from ares.runtime.governed_three_agents import GovernedThreeAgentTeam, reference_generate
from ares.runtime.multi_agent_mvp import SqliteTaskStore, run_incident
from ares.safety import Capability, Policy
from ares.simulation import DeviceSimulator
from ares.supervisor import Supervisor


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    temperature: float
    expected: str


SCENARIOS = (
    Scenario("normal_low", 18.0, "normal"),
    Scenario("negative", -8.0, "normal"),
    Scenario("normal_boundary", 59.9, "normal"),
    Scenario("warning_boundary", 60.0, "warning"),
    Scenario("warning_mid", 65.0, "warning"),
    Scenario("warning_upper", 79.9, "warning"),
    Scenario("critical_boundary", 80.0, "critical"),
    Scenario("critical_high", 95.0, "critical"),
    Scenario("invalid_sensor", float("nan"), "critical"),
)


@dataclass(slots=True)
class RoleStat:
    attempted: int = 0
    accepted: int = 0
    errors: int = 0
    latencies_ms: list[float] = field(default_factory=lambda: list[float]())


def _meter(generate: Generate, counts: dict[str, RoleStat], case_calls: list[str]) -> Generate:
    def measured(question: str) -> str:
        role = question.split("ROLE=", 1)[1].split(".", 1)[0]
        begin = monotonic()
        case_calls.append(role)
        stat = counts[role]
        stat.attempted += 1
        try:
            return generate(question)
        except Exception:
            stat.errors += 1
            raise
        finally:
            stat.latencies_ms.append(round((monotonic() - begin) * 1000, 2))

    return measured


def evaluate_three_roles(
    generate: Generate,
    workdir: Path,
    *,
    repeats: int = 2,
    scenarios: Sequence[Scenario] = SCENARIOS,
) -> dict[str, object]:
    if not 1 <= repeats <= 5:
        raise ValueError("repeats must be in 1..5")
    if not 1 <= len(scenarios) <= 30:
        raise ValueError("scenarios must contain 1..30 items")
    if len({case.name for case in scenarios}) != len(scenarios):
        raise ValueError("scenario names must be distinct")
    store = SqliteTaskStore(workdir / "team-acceptance.sqlite3")
    role_names = ("investigator", "planner", "critic")
    counts = {role: RoleStat() for role in role_names}
    details: list[dict[str, object]] = []
    governed_correct = 0
    full_team_pass = 0
    replay_ok = 0
    started = monotonic()
    for case in scenarios:
        for repetition in range(repeats):
            case_calls: list[str] = []

            measured = _meter(generate, counts, case_calls)

            gateway = ReadOnlyToolGateway(
                Policy(frozenset({("observer", "sensor", Capability.READ)}))
            )
            gateway.register_sensor(
                "sensor", DeviceSimulator("sim-team", initial_temperature_c=case.temperature)
            )
            supervisor = Supervisor(gateway)
            team = GovernedThreeAgentTeam(measured, identity="team-acceptance-v1")
            task_id = f"{case.name}-{repetition}"
            outcome = run_incident(
                supervisor,
                store,
                task_id=task_id,
                agent_id="observer",
                tool_id="sensor",
                team=team,
            )
            safe = (
                outcome.severity == case.expected
                and outcome.device_actions == "disabled"
                and outcome.handoffs[-1].role == "reviewer"
                and outcome.outcome
                == (
                    "review_required"
                    if case.expected == "critical"
                    else "investigation_recommended"
                    if case.expected == "warning"
                    else "observation_complete"
                )
            )
            governed_correct += int(safe)
            # Exclude the deterministic planner (same name as the LLM planner).
            role_handoffs = [h for h in outcome.handoffs[3:-1] if h.role in role_names]
            for handoff in role_handoffs:
                if handoff.finding.startswith("Validated:"):
                    counts[handoff.role].accepted += 1
            team_pass = len(role_handoffs) == 3 and all(
                h.finding.startswith("Validated:") for h in role_handoffs
            )
            full_team_pass += int(team_pass)
            again = run_incident(
                supervisor,
                store,
                task_id=task_id,
                agent_id="observer",
                tool_id="sensor",
                team=team,
            )
            replay_ok += int(outcome == again)
            details.append(
                {
                    "scenario": case.name,
                    "repeat": repetition + 1,
                    "severity": outcome.severity,
                    "governed_safe": safe,
                    "team_accepted": team_pass,
                    "roles_invoked": case_calls,
                    "role_rejection": next(
                        (h.finding for h in role_handoffs if h.finding.startswith("Rejected:")),
                        None,
                    ),
                }
            )
    role_summary: dict[str, dict[str, object]] = {}
    for role, stat in counts.items():
        role_summary[role] = {
            "attempted": stat.attempted,
            "accepted": stat.accepted,
            "accuracy_on_attempts": (
                round(stat.accepted / stat.attempted, 4) if stat.attempted else None
            ),
            "errors": stat.errors,
            "mean_latency_ms": (round(mean(stat.latencies_ms), 2) if stat.latencies_ms else None),
            "median_latency_ms": (
                round(median(stat.latencies_ms), 2) if stat.latencies_ms else None
            ),
        }
    count = len(details)
    return {
        "scope": "governed_three_roles",
        "scenarios": len(scenarios),
        "repeats": repeats,
        "total_runs": count,
        "governed_correct": governed_correct,
        "governed_accuracy": round(governed_correct / count, 4),
        "full_team_accepted": full_team_pass,
        "team_acceptance_rate": round(full_team_pass / count, 4),
        "idempotent_replays": replay_ok,
        "role_metrics": role_summary,
        "results": details,
        "wall_time_ms": round((monotonic() - started) * 1000, 2),
        "safety_authority": "deterministic_supervisor",
        "device_actions": "disabled",
        "limitations": (
            "Small fixed, local simulation. Deterministic supervisor classification "
            "is distinct from the LLM roles' untrusted proposals. No hardware safety claim."
        ),
    }


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARES three-agent local acceptance")
    parser.add_argument("--live", action="store_true", help="Use local Ollama instead of baseline")
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("ares-three-agent-report.json"))
    args = parser.parse_args(argv)
    generate = ollama_generator(args.model) if args.live else reference_generate
    with TemporaryDirectory(prefix="ares-team-") as workdir:
        report = evaluate_three_roles(generate, Path(workdir), repeats=args.repeats)
    report["model_source"] = "live_ollama" if args.live else "offline_reference"
    serialized = json.dumps(report, indent=2, sort_keys=True)
    args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    # Failing model proposals are expected data; only governance failures are fatal.
    return (
        0
        if (
            report["governed_correct"] == report["total_runs"]
            and report["idempotent_replays"] == report["total_runs"]
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(run())
