"""Deterministic, synchronous execution of one task.

This layer deliberately does not provide tool access, retries, or device commands.
"""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from ares.core.errors import DomainError
from ares.core.events import Event, EventKind
from ares.core.models import Task, TaskStatus

TaskHandler = Callable[[Task], None]
EventFactory = Callable[[str, EventKind, str], Event]


def new_event(task_id: str, kind: EventKind, detail: str = "") -> Event:
    """Create a uniquely identified event."""
    return Event(id=str(uuid4()), task_id=task_id, kind=kind, detail=detail)


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Final task snapshot and ordered events for a single execution."""

    task: Task
    events: tuple[Event, ...]
    error: str | None = None


class TaskExecutor:
    """Execute exactly one pending task through an injected handler."""

    def __init__(self, event_factory: EventFactory = new_event) -> None:
        self._event_factory = event_factory

    def execute(self, task: Task, handler: TaskHandler) -> ExecutionResult:
        """Run a task, converting normal handler exceptions into failure results.

        The handler receives a RUNNING snapshot. BaseException subclasses such
        as KeyboardInterrupt are intentionally not swallowed.
        """
        if task.status is not TaskStatus.PENDING:
            raise DomainError("Only pending tasks may be executed")

        running = task.transition_to(TaskStatus.RUNNING)
        started = self._event_factory(running.id, EventKind.TASK_STARTED, "")
        try:
            handler(running)
        except Exception as exc:
            failed = running.transition_to(TaskStatus.FAILED)
            message = f"{type(exc).__name__}: {exc}"
            failure = self._event_factory(failed.id, EventKind.TASK_FAILED, message)
            return ExecutionResult(task=failed, events=(started, failure), error=message)

        completed = running.transition_to(TaskStatus.COMPLETED)
        finished = self._event_factory(completed.id, EventKind.TASK_COMPLETED, "")
        return ExecutionResult(task=completed, events=(started, finished))
