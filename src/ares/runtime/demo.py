"""Local, offline demonstration of the durable incident workflow."""

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from ares.integrations import ReadOnlyToolGateway
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
    args = parser.parse_args(argv)

    device = DeviceSimulator("demo-sim", initial_temperature_c=args.temperature)
    gateway = ReadOnlyToolGateway(
        Policy(frozenset({("observer", "sensor", Capability.READ)}))
    )
    gateway.register_sensor("sensor", device)
    store = SqliteTaskStore(args.db)
    report = run_incident(
        Supervisor(gateway),
        store,
        task_id=args.task_id,
        agent_id="observer",
        tool_id="sensor",
        recover=args.recover,
    )
    print(
        json.dumps(
            {"report": asdict(report), "tasks": store.summary(),
             "execution_scope": "offline_deterministic_simulation"},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
