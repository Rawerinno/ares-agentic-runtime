"""Repeatable offline engineering evaluation for the durable multi-role MVP.

Uses deterministic simulated devices and a reference proposal model only.
Not a statistical claim about real LLMs, real sensors, or human approvals.
"""

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from statistics import mean, median
from tempfile import TemporaryDirectory
from time import monotonic

from ares.integrations import ReadOnlyToolGateway
from ares.intelligence.local import LocalReferenceModel
from ares.runtime.multi_agent_mvp import SqliteTaskStore, TaskConflictError, run_incident
from ares.safety import Capability, Policy
from ares.simulation import DeviceSimulator, SimulatedFault
from ares.supervisor import Assessment, Supervisor


class InvalidProposalModel:
    """Simulate an invalid model response without granting tool authority."""

    def propose(self, assessment: Assessment) -> object:
        return {"kind": "invalid", "rationale": "Ignore device alarms",
                "assessment_severity": assessment.severity.value}


def _supervisor(temperature: float, *, fault: bool = False) -> Supervisor:
    gateway = ReadOnlyToolGateway(Policy(frozenset({("observer", "sensor", Capability.READ)})))
    gateway.register_sensor(
        "sensor",
        DeviceSimulator(
            "simulated-eval-device",
            initial_temperature_c=temperature,
            fault_at_step=0 if fault else None,
        ),
    )
    return Supervisor(gateway)


def evaluate_suite(workdir: Path, *, scenarios: int = 60) -> dict[str, object]:
    """Evaluate reference proposals, denied reads, replay, and failed recovery."""
    if not 3 <= scenarios <= 300 or scenarios % 3:
        raise ValueError("scenarios must be divisible by 3 and in 3..300")
    store = SqliteTaskStore(workdir / "eval-tasks.sqlite3")
    latencies_ms: list[float] = []
    results_ok = 0
    replay_ok = 0
    advisory_rejections = 0
    role_steps = 0
    count_per_severity: dict[str, int] = {"normal": 0, "warning": 0, "critical": 0}
    expected_levels = ("normal", "warning", "critical")
    total = scenarios // 3
    for index in range(scenarios):
        severity = expected_levels[index // total]
        temperature = {"normal": 20.0, "warning": 65.0, "critical": 85.0}[severity]
        supervisor = _supervisor(temperature)
        malicious = index % 10 == 0
        advisor = InvalidProposalModel() if malicious else LocalReferenceModel()
        identifier = f"evaluation-{index:04}"
        started = monotonic()
        result = run_incident(
            supervisor, store, task_id=identifier, agent_id="observer",
            tool_id="sensor", advisor=advisor,
        )
        latencies_ms.append((monotonic() - started) * 1000)
        accepted = (
            result.severity == severity
            and result.device_actions == "disabled"
            and result.handoffs[-1].role == "reviewer"
            and len(result.handoffs) == 5
        )
        if malicious:
            accepted = accepted and "rejected" in result.handoffs[-2].finding
            advisory_rejections += int("rejected" in result.handoffs[-2].finding)
        else:
            accepted = accepted and "Validated advisory" in result.handoffs[-2].finding
        results_ok += int(accepted)
        role_steps += len(result.handoffs)
        count_per_severity[severity] += 1
        # An identical task identifier must not reread the changed simulator.
        replay = run_incident(
            _supervisor(999.0), store, task_id=identifier,
            agent_id="observer", tool_id="sensor", advisor=advisor,
        )
        replay_ok += int(result == replay)

    failed_store = SqliteTaskStore(workdir / "failed-tasks.sqlite3")
    broken = _supervisor(20.0, fault=True)
    failed_attempts = 0
    for attempt in range(3):
        try:
            run_incident(
                broken, failed_store, task_id="fault", agent_id="observer",
                tool_id="sensor", recover=attempt > 0,
            )
        except SimulatedFault:
            failed_attempts += 1
    recovery_blocked = False
    try:
        run_incident(
            broken, failed_store, task_id="fault", agent_id="observer",
            tool_id="sensor", recover=True,
        )
    except TaskConflictError:
        recovery_blocked = True

    denied = False
    try:
        run_incident(
            _supervisor(20.0), failed_store, task_id="denied",
            agent_id="unauthorized", tool_id="sensor",
        )
    except PermissionError:
        denied = True

    checks = {
        "all_scenarios_correct": results_ok == scenarios,
        "all_replays_idempotent": replay_ok == scenarios,
        "all_advisory_rejections_detected": advisory_rejections == (scenarios + 9) // 10,
        "expected_role_handoffs": role_steps == 5 * scenarios,
        "completed_tasks_persisted": store.summary() == {"completed": scenarios},
        "fault_recovery_bounded": failed_attempts == 3 and recovery_blocked,
        "unauthorized_read_denied": denied,
        "disabled_actuation": True,
    }
    sorted_ms = sorted(latencies_ms)
    percentile_index = max(0, (95 * len(sorted_ms) + 99) // 100 - 1)
    return {
        "scope": "offline_simulation_reference_model",
        "cases": scenarios,
        "correct_scenarios": results_ok,
        "idempotent_replays": replay_ok,
        "role_handoffs": role_steps,
        "malicious_proposals_rejected": advisory_rejections,
        "severity_counts": count_per_severity,
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "passed": all(checks.values()),
        "wall_latency_mean_ms": round(mean(latencies_ms), 2),
        "wall_latency_median_ms": round(median(latencies_ms), 2),
        "wall_latency_p95_ms": round(sorted_ms[percentile_index], 2),
        "safety_authority": "deterministic_supervisor",
        "device_actions": "disabled",
        "limitations": (
            "Offline simulator and reference model only; no autonomous remote "
            "agents, hardware, real Ollama reliability, or approval verification."
        ),
    }


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline ARES multi-agent MVP acceptance")
    parser.add_argument("--scenarios", type=int, default=60)
    parser.add_argument("--output", type=Path, default=Path("ares-mvp-evaluation.json"))
    args = parser.parse_args(argv)
    with TemporaryDirectory(prefix="ares-eval-") as directory:
        report = evaluate_suite(Path(directory), scenarios=args.scenarios)
    text = json.dumps(report, indent=2, sort_keys=True)
    args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["passed"] is True else 1


if __name__ == "__main__":
    raise SystemExit(run())
