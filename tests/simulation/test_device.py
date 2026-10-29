"""Deterministic simulator and execution integration tests."""

import pytest

from ares.core import Task, TaskStatus
from ares.core.execution import TaskExecutor
from ares.simulation import DeviceSimulator, SimulatedFault


def test_sensor_is_repeatable_without_advancing() -> None:
    device = DeviceSimulator("sensor-a")
    assert device.read() == device.read()
    assert device.read().temperature_c == 20.0
    assert device.read().step == 0


def test_advance_changes_temperature_and_step() -> None:
    device = DeviceSimulator("sensor-a", increment_c=2.0)
    device.advance()
    assert device.read().step == 1
    assert device.read().temperature_c == 22.0


def test_fault_injection_at_selected_step() -> None:
    device = DeviceSimulator("sensor-a", fault_at_step=2)
    device.advance()
    assert device.read().healthy
    device.advance()
    with pytest.raises(SimulatedFault, match="step 2"):
        device.read()


def test_immediate_fault() -> None:
    with pytest.raises(SimulatedFault):
        DeviceSimulator("sensor-a", fault_at_step=0).read()


@pytest.mark.parametrize("name", ["", "  "])
def test_invalid_device_identifier(name: str) -> None:
    with pytest.raises(ValueError):
        DeviceSimulator(name)


def test_negative_fault_step_is_rejected() -> None:
    with pytest.raises(ValueError):
        DeviceSimulator("sensor-a", fault_at_step=-1)


def test_executor_observes_simulator() -> None:
    device = DeviceSimulator("sensor-a")
    readings: list[float] = []

    def inspect(item: Task) -> None:
        readings.append(device.read().temperature_c)

    result = TaskExecutor().execute(Task("t1", "a1", "Inspect sensor"), inspect)
    assert readings == [20.0]
    assert result.task.status is TaskStatus.COMPLETED


def test_simulated_fault_becomes_task_failure() -> None:
    device = DeviceSimulator("sensor-a", fault_at_step=0)

    def inspect(item: Task) -> None:
        device.read()

    result = TaskExecutor().execute(Task("t1", "a1", "Inspect sensor"), inspect)
    assert result.task.status is TaskStatus.FAILED
    assert result.error is not None
    assert "SimulatedFault" in result.error
