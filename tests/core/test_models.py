"""Contract tests for agent and task models."""

from dataclasses import FrozenInstanceError

import pytest

from ares.core import Agent, DomainError, InvalidTransitionError, Task, TaskStatus


def test_agent_is_immutable() -> None:
    agent = Agent(id="agent-1", name="Supervisor")
    assert agent.name == "Supervisor"
    with pytest.raises(FrozenInstanceError):
        agent.name = "Changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("agent_id", "name"),
    [("", "Supervisor"), ("   ", "Supervisor"), ("a1", ""), ("a1", "  ")],
)
def test_agent_rejects_blank_fields(agent_id: str, name: str) -> None:
    with pytest.raises(DomainError):
        Agent(id=agent_id, name=name)


@pytest.mark.parametrize(
    ("task_id", "agent_id", "instruction"),
    [("", "a1", "Check"), ("t1", " ", "Check"), ("t1", "a1", "")],
)
def test_task_rejects_blank_fields(task_id: str, agent_id: str, instruction: str) -> None:
    with pytest.raises(DomainError):
        Task(id=task_id, agent_id=agent_id, instruction=instruction)


def test_task_defaults_to_pending_and_moves_through_successful_lifecycle() -> None:
    pending = Task(id="t1", agent_id="a1", instruction="Read sensor")
    running = pending.transition_to(TaskStatus.RUNNING)
    completed = running.transition_to(TaskStatus.COMPLETED)
    assert pending.status is TaskStatus.PENDING
    assert running.status is TaskStatus.RUNNING
    assert completed.status is TaskStatus.COMPLETED
    assert completed.id == pending.id


def test_task_can_fail_after_running() -> None:
    task = Task("t1", "a1", "Read sensor").transition_to(TaskStatus.RUNNING)
    assert task.transition_to(TaskStatus.FAILED).status is TaskStatus.FAILED


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (TaskStatus.PENDING, TaskStatus.COMPLETED),
        (TaskStatus.PENDING, TaskStatus.FAILED),
        (TaskStatus.PENDING, TaskStatus.PENDING),
        (TaskStatus.RUNNING, TaskStatus.RUNNING),
        (TaskStatus.COMPLETED, TaskStatus.RUNNING),
        (TaskStatus.FAILED, TaskStatus.RUNNING),
    ],
)
def test_illegal_transitions_are_rejected(start: TaskStatus, end: TaskStatus) -> None:
    task = Task("t1", "a1", "Read sensor", start)
    with pytest.raises(InvalidTransitionError):
        task.transition_to(end)


def test_task_rejects_unknown_status() -> None:
    with pytest.raises(DomainError):
        Task("t1", "a1", "Read sensor", "unknown")  # type: ignore[arg-type]


def test_transition_rejects_unknown_status() -> None:
    task = Task("t1", "a1", "Read sensor")
    with pytest.raises(InvalidTransitionError):
        task.transition_to("running")  # type: ignore[arg-type]
