"""Synchronous task execution contract tests."""

import pytest

from ares.core import DomainError, Event, EventKind, Task, TaskStatus
from ares.core.execution import TaskExecutor, new_event


def task() -> Task:
    return Task(id="task-1", agent_id="agent-1", instruction="Inspect sensor")


def test_successful_execution() -> None:
    observed: list[TaskStatus] = []

    def handler(item: Task) -> None:
        observed.append(item.status)

    result = TaskExecutor().execute(task(), handler)
    assert observed == [TaskStatus.RUNNING]
    assert result.task.status is TaskStatus.COMPLETED
    assert result.error is None
    assert [event.kind for event in result.events] == [
        EventKind.TASK_STARTED,
        EventKind.TASK_COMPLETED,
    ]
    assert all(event.task_id == "task-1" for event in result.events)
    assert len({event.id for event in result.events}) == 2


def test_failure_is_reported_without_losing_events() -> None:
    def handler(item: Task) -> None:
        raise RuntimeError(f"Device unavailable for {item.id}")

    result = TaskExecutor().execute(task(), handler)
    assert result.task.status is TaskStatus.FAILED
    assert result.error == "RuntimeError: Device unavailable for task-1"
    assert [event.kind for event in result.events] == [
        EventKind.TASK_STARTED,
        EventKind.TASK_FAILED,
    ]
    assert result.events[-1].detail == result.error


@pytest.mark.parametrize(
    "status",
    [TaskStatus.RUNNING, TaskStatus.COMPLETED, TaskStatus.FAILED],
)
def test_non_pending_task_never_invokes_handler(status: TaskStatus) -> None:
    invoked = False

    def handler(item: Task) -> None:
        nonlocal invoked
        invoked = True

    with pytest.raises(DomainError):
        TaskExecutor().execute(Task("t1", "a1", "Inspect", status), handler)
    assert invoked is False


def test_injected_event_factory_preserves_order() -> None:
    sequence: list[str] = []

    def factory(task_id: str, kind: EventKind, detail: str) -> Event:
        sequence.append(kind.value)
        return Event(id=str(len(sequence)), task_id=task_id, kind=kind, detail=detail)

    result = TaskExecutor(event_factory=factory).execute(task(), lambda item: None)
    assert sequence == ["task.started", "task.completed"]
    assert [event.id for event in result.events] == ["1", "2"]


def test_new_event_generates_distinct_identifiers() -> None:
    first = new_event("t1", EventKind.TASK_STARTED)
    second = new_event("t1", EventKind.TASK_STARTED)
    assert first.id != second.id


def test_keyboard_interrupt_is_not_swallowed() -> None:
    def handler(item: Task) -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        TaskExecutor().execute(task(), handler)
