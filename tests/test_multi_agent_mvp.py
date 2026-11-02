"""Offline integration tests for durable multi-role simulated incidents."""

from pathlib import Path

import pytest

from ares.integrations import ReadOnlyToolGateway
from ares.runtime.multi_agent_mvp import SqliteTaskStore, TaskConflictError, run_incident
from ares.safety import Capability, Policy
from ares.simulation import DeviceSimulator, SimulatedFault
from ares.supervisor import Supervisor


def system(
    tmp_path: Path, *,
    temperature: float = 20.0, fault_at_step: int | None = None
) -> tuple[DeviceSimulator, Supervisor, SqliteTaskStore]:
    device = DeviceSimulator(
        "sim-01", initial_temperature_c=temperature, fault_at_step=fault_at_step
    )
    gateway = ReadOnlyToolGateway(
        Policy(frozenset({("observer", "sensor", Capability.READ)}))
    )
    gateway.register_sensor("sensor", device)
    return device, Supervisor(gateway), SqliteTaskStore(tmp_path / "tasks.sqlite3")


@pytest.mark.parametrize(
    ("temp", "severity", "outcome"),
    [
        (20.0, "normal", "observation_complete"),
        (60.0, "warning", "investigation_recommended"),
        (80.0, "critical", "review_required"),
    ],
)
def test_four_role_handoffs_and_no_actuation(
    tmp_path: Path, temp: float, severity: str, outcome: str
) -> None:
    _, supervisor, store = system(tmp_path, temperature=temp)
    result = run_incident(
        supervisor, store, task_id="incident-a", agent_id="observer", tool_id="sensor"
    )
    assert result.severity == severity
    assert result.outcome == outcome
    assert result.device_actions == "disabled"
    assert tuple(item.role for item in result.handoffs) == (
        "observer", "diagnostician", "planner", "reviewer"
    )
    assert store.summary() == {"completed": 1}


def test_replay_is_idempotent_and_never_rereads_sensor(tmp_path: Path) -> None:
    device, supervisor, store = system(tmp_path)
    first = run_incident(
        supervisor, store, task_id="repeat", agent_id="observer", tool_id="sensor"
    )
    device.advance()
    again = run_incident(
        supervisor, store, task_id="repeat", agent_id="observer", tool_id="sensor"
    )
    assert first == again
    assert again.observed_step == 0
    assert again.temperature_c == 20


def test_saved_output_survives_store_reopening(tmp_path: Path) -> None:
    _, supervisor, store = system(tmp_path, temperature=81)
    original = run_incident(
        supervisor, store, task_id="persist", agent_id="observer", tool_id="sensor"
    )
    restarted = SqliteTaskStore(tmp_path / "tasks.sqlite3")
    restored = run_incident(
        supervisor, restarted, task_id="persist", agent_id="observer", tool_id="sensor"
    )
    assert restored == original


def test_task_request_fingerprint_prevents_reassignment(tmp_path: Path) -> None:
    _, supervisor, store = system(tmp_path)
    run_incident(supervisor, store, task_id="same", agent_id="observer", tool_id="sensor")
    with pytest.raises(TaskConflictError, match="different request"):
        run_incident(supervisor, store, task_id="same", agent_id="observer", tool_id="other")


def test_failed_sensor_read_requires_explicit_recovery(tmp_path: Path) -> None:
    device, supervisor, store = system(tmp_path, fault_at_step=0)
    with pytest.raises(SimulatedFault):
        run_incident(supervisor, store, task_id="failed", agent_id="observer", tool_id="sensor")
    assert store.summary() == {"failed": 1}
    with pytest.raises(TaskConflictError, match="explicit recovery"):
        run_incident(supervisor, store, task_id="failed", agent_id="observer", tool_id="sensor")
    # A recovered task still fails when the simulated fault is persistent.
    with pytest.raises(SimulatedFault):
        run_incident(
            supervisor, store, task_id="failed", agent_id="observer",
            tool_id="sensor", recover=True,
        )
    with pytest.raises(SimulatedFault):
        run_incident(
            supervisor, store, task_id="failed", agent_id="observer",
            tool_id="sensor", recover=True,
        )
    with pytest.raises(TaskConflictError, match="budget exhausted"):
        run_incident(
            supervisor, store, task_id="failed", agent_id="observer",
            tool_id="sensor", recover=True,
        )
    assert device is not None


def test_ungranted_read_never_runs_roles(tmp_path: Path) -> None:
    _, supervisor, store = system(tmp_path)
    with pytest.raises(PermissionError):
        run_incident(
            supervisor, store, task_id="no-grant", agent_id="untrusted", tool_id="sensor"
        )
    assert store.summary() == {"failed": 1}


def test_reject_symlink_task_database(tmp_path: Path) -> None:
    target = tmp_path / "real.sqlite"
    target.touch()
    link = tmp_path / "link.sqlite"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        SqliteTaskStore(link)
