"""Supervisor assessment, authorization and execution integration tests."""

import pytest

from ares.core import Task, TaskStatus
from ares.core.execution import TaskExecutor
from ares.integrations import ReadOnlyToolGateway
from ares.safety import AuthorizationError, Capability, Policy
from ares.simulation import DeviceSimulator
from ares.supervisor import Severity, Supervisor


def supervisor(temperature: float, *, granted: bool = True) -> Supervisor:
    grants: frozenset[tuple[str, str, Capability]] = (
        frozenset({("supervisor", "temperature", Capability.READ)}) if granted else frozenset()
    )
    gateway = ReadOnlyToolGateway(Policy(grants))
    gateway.register_sensor(
        "temperature",
        DeviceSimulator("simulated-sensor", initial_temperature_c=temperature),
    )
    return Supervisor(gateway)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (20.0, Severity.NORMAL),
        (59.9, Severity.NORMAL),
        (60.0, Severity.WARNING),
        (79.9, Severity.WARNING),
        (80.0, Severity.CRITICAL),
        (95.0, Severity.CRITICAL),
        (float("nan"), Severity.CRITICAL),
        (float("inf"), Severity.CRITICAL),
    ],
)
def test_temperature_classification(value: float, expected: Severity) -> None:
    result = supervisor(value).assess(agent_id="supervisor", tool_id="temperature")
    assert result.severity is expected
    assert result.recommendation


def test_no_permission_means_no_observation() -> None:
    with pytest.raises(AuthorizationError):
        supervisor(20.0, granted=False).assess(agent_id="supervisor", tool_id="temperature")


@pytest.mark.parametrize(
    ("warning", "critical"),
    [(80.0, 80.0), (90.0, 80.0), (float("nan"), 80.0), (50.0, float("inf"))],
)
def test_invalid_thresholds(warning: float, critical: float) -> None:
    gateway = ReadOnlyToolGateway(Policy())
    with pytest.raises(ValueError):
        Supervisor(gateway, warning_c=warning, critical_c=critical)


def test_supervisor_runs_inside_task_executor() -> None:
    agent = supervisor(85.0)
    reports: list[Severity] = []

    def inspect(task: Task) -> None:
        reports.append(agent.assess(agent_id=task.agent_id, tool_id="temperature").severity)

    result = TaskExecutor().execute(Task("task-1", "supervisor", "Inspect temperature"), inspect)
    assert result.task.status is TaskStatus.COMPLETED
    assert reports == [Severity.CRITICAL]


def test_denial_produces_failed_task() -> None:
    agent = supervisor(20.0, granted=False)

    def inspect(task: Task) -> None:
        agent.assess(agent_id=task.agent_id, tool_id="temperature")

    result = TaskExecutor().execute(Task("task-1", "supervisor", "Inspect"), inspect)
    assert result.task.status is TaskStatus.FAILED
    assert result.error is not None
    assert "AuthorizationError" in result.error
