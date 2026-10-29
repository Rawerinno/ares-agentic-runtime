"""Gateway tests show that denied operations do not reach the sensor."""

import pytest

from ares.core import Task, TaskStatus
from ares.core.execution import TaskExecutor
from ares.integrations import ReadOnlyToolGateway, ToolNotFoundError
from ares.safety import AuthorizationError, Capability, Policy, RiskLevel
from ares.simulation import DeviceSimulator, DeviceSnapshot


class CountingSensor(DeviceSimulator):
    def __init__(self) -> None:
        super().__init__("s1")
        self.reads = 0

    def read(self) -> DeviceSnapshot:
        self.reads += 1
        return super().read()


def gateway() -> ReadOnlyToolGateway:
    return ReadOnlyToolGateway(Policy(frozenset({("a1", "sensor.temperature", Capability.READ)})))


def test_authorized_sensor_read() -> None:
    g = gateway()
    g.register_sensor("sensor.temperature", DeviceSimulator("s1"))
    result = g.read_sensor(agent_id="a1", tool_id="sensor.temperature")
    assert result.tool_id == "sensor.temperature"
    assert result.snapshot.temperature_c == 20.0


def test_denied_read_never_calls_sensor() -> None:
    sensor = CountingSensor()
    g = gateway()
    g.register_sensor("sensor.temperature", sensor)
    with pytest.raises(AuthorizationError):
        g.read_sensor(agent_id="a2", tool_id="sensor.temperature")
    assert sensor.reads == 0


def test_high_risk_read_fails_closed() -> None:
    sensor = CountingSensor()
    g = gateway()
    g.register_sensor("sensor.temperature", sensor)
    with pytest.raises(AuthorizationError):
        g.read_sensor(agent_id="a1", tool_id="sensor.temperature", risk=RiskLevel.HIGH)
    assert sensor.reads == 0


def test_unknown_tool_rejected() -> None:
    with pytest.raises(ToolNotFoundError):
        gateway().read_sensor(agent_id="a1", tool_id="sensor.temperature")


def test_duplicate_and_blank_registration_rejected() -> None:
    g = gateway()
    g.register_sensor("sensor.temperature", DeviceSimulator("s1"))
    with pytest.raises(ValueError):
        g.register_sensor("sensor.temperature", DeviceSimulator("s2"))
    with pytest.raises(ValueError):
        g.register_sensor(" ", DeviceSimulator("s2"))


def test_end_to_end_task_read() -> None:
    g = gateway()
    g.register_sensor("sensor.temperature", DeviceSimulator("s1"))
    readings: list[float] = []

    def handler(item: Task) -> None:
        result = g.read_sensor(agent_id=item.agent_id, tool_id="sensor.temperature")
        readings.append(result.snapshot.temperature_c)

    result = TaskExecutor().execute(Task("task1", "a1", "Inspect temperature"), handler)
    assert result.task.status is TaskStatus.COMPLETED
    assert readings == [20.0]


def test_denied_tool_execution_records_failed_task() -> None:
    g = gateway()
    sensor = CountingSensor()
    g.register_sensor("sensor.temperature", sensor)

    def handler(item: Task) -> None:
        g.read_sensor(agent_id=item.agent_id, tool_id="sensor.temperature")

    result = TaskExecutor().execute(Task("task1", "outsider", "Read"), handler)
    assert result.task.status is TaskStatus.FAILED
    assert result.error is not None
    assert "AuthorizationError" in result.error
    assert sensor.reads == 0
