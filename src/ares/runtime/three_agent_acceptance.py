"""Reproducible read-only acceptance of three governed model roles.

Offline uses a deterministic reference; --live uses the local Ollama model.
Safety is measured separately from raw model-role acceptance.
"""

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path
from statistics import mean, median
from tempfile import TemporaryDirectory
from time import monotonic

from ares.evaluation.ollama_capability_boundary import Generate
from ares.integrations import ReadOnlyToolGateway
from ares.runtime.governed_three_agents import GovernedThreeAgentTeam, reference_generate
from ares.runtime.multi_agent_mvp import SqliteTaskStore, run_incident
from ares.runtime.three_agent_ollama import ollama_three_role_generator
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


def _bounded_role_value(role: str, answer: str) -> str:
    """Retain only allowlisted enum values, never arbitrary model text."""
    allowlists = {
        "investigator": ("hypothesis", {"stable", "thermal_load", "sensor_fault"}),
        "planner": ("plan", {"monitor", "inspect", "human_review"}),
        "critic": ("verdict", {"consistent", "inconsistent"}),
    }
    if role not in allowlists or len(answer) > 512:
        return "unrecognized"
    try:
        value: object = json.loads(answer)
    except (ValueError, TypeError):
        return "unrecognized"
    if not isinstance(value, dict):
        return "unrecognized"
    field, allowed = allowlists[role]
    actual = value.get(field)
    return actual if isinstance(actual, str) and actual in allowed else "unrecognized"


def _meter(
    generate: Generate,
    counts: dict[str, RoleStat],
    case_calls: list[str],
    proposals: list[dict[str, str]] | None = None,
) -> Generate:
    def measured(question: str) -> str:
        role = question.split("ROLE=", 1)[1].split(".", 1)[0]
        begin = monotonic()
        case_calls.append(role)
        stat = counts[role]
        stat.attempted += 1
        try:
            answer = generate(question)
            if proposals is not None:
                proposals.append({"role": role, "proposed": _bounded_role_value(role, answer)})
            return answer
        except Exception:
            stat.errors += 1
            raise
        finally:
            stat.latencies_ms.append(round((monotonic() - begin) * 1000, 2))

    return measured


def _isolated_target(
    generate: Generate,
    counts: dict[str, RoleStat],
    target_role: str,
    calls: list[str],
    proposals: list[dict[str, str]],
) -> Generate:
    """Only target role reaches the real generator; peers use a reference."""
    measured = _meter(generate, counts, calls, proposals)

    def generate_target(question: str) -> str:
        role = question.split("ROLE=", 1)[1].split(".", 1)[0]
        return measured(question) if role == target_role else reference_generate(question)

    return generate_target


def _investigator_confusion(
    details: list[dict[str, object]],
    isolated_results: list[dict[str, object]],
) -> dict[str, dict[str, int]]:
    """Count only allowlisted hypotheses from the evaluation; no free text."""
    selected = isolated_results if isolated_results else details
    result: dict[str, dict[str, int]] = {}
    for row in selected:
        scenario = row["scenario"]
        if not isinstance(scenario, str):
            continue
        expected = row.get("expected_hypothesis")
        if expected not in ("sensor_fault", "stable", "thermal_load"):
            continue
        proposed: str | None = None
        if isolated_results:
            if row.get("target_role") != "investigator":
                continue
            value = row.get("bounded_proposal")
            if isinstance(value, str):
                proposed = value
        else:
            proposals = row.get("bounded_proposals")
            if isinstance(proposals, list):
                for item in proposals:
                    if isinstance(item, dict) and item.get("role") == "investigator":
                        candidate = item.get("proposed")
                        if isinstance(candidate, str):
                            proposed = candidate
                        break
        key = proposed or "no_response"
        bucket = result.setdefault(expected, {})
        bucket[key] = bucket.get(key, 0) + 1
    return result


def evaluate_three_roles(
    generate: Generate,
    workdir: Path,
    *,
    repeats: int = 2,
    scenarios: Sequence[Scenario] = SCENARIOS,
    role_only: bool = False,
    probe_roles: bool = False,
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
    isolated_counts = {role: RoleStat() for role in role_names}
    isolated_results: list[dict[str, object]] = []
    details: list[dict[str, object]] = []
    governed_correct = 0
    full_team_pass = 0
    replay_ok = 0
    rejection_counts: dict[str, dict[str, int]] = {role: {} for role in role_names}
    started = monotonic()
    for case in scenarios:
        for repetition in range(repeats):
            expected_hypothesis = (
                "sensor_fault"
                if not isfinite(case.temperature)
                else "stable"
                if case.expected == "normal"
                else "thermal_load"
            )
            case_calls: list[str] = []
            case_proposals: list[dict[str, str]] = []

            measured = _meter(generate, counts, case_calls, case_proposals)

            gateway = ReadOnlyToolGateway(
                Policy(frozenset({("observer", "sensor", Capability.READ)}))
            )
            gateway.register_sensor(
                "sensor", DeviceSimulator("sim-team", initial_temperature_c=case.temperature)
            )
            supervisor = Supervisor(gateway)
            team = GovernedThreeAgentTeam(
                measured, identity="team-acceptance-v2", role_only=role_only
            )
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
                elif handoff.finding.startswith("Rejected:"):
                    code = handoff.finding.removeprefix("Rejected: ")
                    bucket = rejection_counts[handoff.role]
                    bucket[code] = bucket.get(code, 0) + 1
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
            if probe_roles:
                assessment = supervisor.assess(agent_id="observer", tool_id="sensor")
                for target_role in role_names:
                    calls: list[str] = []
                    probe_proposals: list[dict[str, str]] = []

                    isolated = _isolated_target(
                        generate, isolated_counts, target_role, calls, probe_proposals
                    )

                    probe = GovernedThreeAgentTeam(
                        isolated, identity="isolated-probe-v1", role_only=role_only
                    ).evaluate(assessment)
                    own = next(
                        (h for h in probe.handoffs if h.role == target_role),
                        None,
                    )
                    accepted = own is not None and own.finding.startswith("Validated:")
                    if accepted:
                        isolated_counts[target_role].accepted += 1
                    isolated_results.append(
                        {
                            "scenario": case.name,
                            "repeat": repetition + 1,
                            "target_role": target_role,
                            "expected_hypothesis": expected_hypothesis,
                            "accepted": accepted,
                            "diagnostic": (
                                own.finding if own is not None and not accepted else None
                            ),
                            "real_model_calls": len(calls),
                            "bounded_proposal": (
                                probe_proposals[0]["proposed"] if probe_proposals else None
                            ),
                        }
                    )
            details.append(
                {
                    "scenario": case.name,
                    "repeat": repetition + 1,
                    "expected_hypothesis": expected_hypothesis,
                    "severity": outcome.severity,
                    "governed_safe": safe,
                    "team_accepted": team_pass,
                    "roles_invoked": case_calls,
                    "bounded_proposals": case_proposals,
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
        "role_contract": "role_only" if role_only else "legacy_severity_echo",
        "scenarios": len(scenarios),
        "repeats": repeats,
        "total_runs": count,
        "governed_correct": governed_correct,
        "governed_accuracy": round(governed_correct / count, 4),
        "full_team_accepted": full_team_pass,
        "team_acceptance_rate": round(full_team_pass / count, 4),
        "idempotent_replays": replay_ok,
        "role_metrics": role_summary,
        "isolated_role_probes": isolated_results if probe_roles else None,
        "isolated_role_metrics": (
            {
                name: {
                    "attempted": stat.attempted,
                    "accepted": stat.accepted,
                    "errors": stat.errors,
                }
                for name, stat in isolated_counts.items()
            }
            if probe_roles
            else None
        ),
        "rejection_counts": rejection_counts,
        "investigator_confusion": _investigator_confusion(details, isolated_results),
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
    parser.add_argument("--role-contract", choices=("role_only", "legacy"), default="role_only")
    parser.add_argument(
        "--probe-roles",
        action="store_true",
        help="Separately evaluate each model role against reference-validated peers",
    )
    parser.add_argument("--output", type=Path, default=Path("ares-three-agent-report.json"))
    args = parser.parse_args(argv)
    role_only = args.role_contract == "role_only"
    generate = (
        ollama_three_role_generator(args.model, role_only=role_only)
        if args.live
        else reference_generate
    )
    with TemporaryDirectory(prefix="ares-team-") as workdir:
        report = evaluate_three_roles(
            generate,
            Path(workdir),
            repeats=args.repeats,
            role_only=role_only,
            probe_roles=args.probe_roles,
        )
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
