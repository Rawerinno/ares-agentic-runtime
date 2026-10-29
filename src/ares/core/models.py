"""Immutable agent and task domain models."""

from dataclasses import dataclass, replace
from enum import StrEnum

from ares.core.errors import DomainError, InvalidTransitionError


def _require_text(value: str, field: str) -> None:
    if not value.strip():
        raise DomainError(f"{field} must not be blank")


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


_ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PENDING: frozenset({TaskStatus.RUNNING}),
    TaskStatus.RUNNING: frozenset({TaskStatus.COMPLETED, TaskStatus.FAILED}),
    TaskStatus.COMPLETED: frozenset(),
    TaskStatus.FAILED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class Agent:
    """An identifiable agent; execution details belong to later layers."""

    id: str
    name: str

    def __post_init__(self) -> None:
        _require_text(self.id, "agent.id")
        _require_text(self.name, "agent.name")


@dataclass(frozen=True, slots=True)
class Task:
    """A unit of assigned work with a controlled lifecycle."""

    id: str
    agent_id: str
    instruction: str
    status: TaskStatus = TaskStatus.PENDING

    def __post_init__(self) -> None:
        _require_text(self.id, "task.id")
        _require_text(self.agent_id, "task.agent_id")
        _require_text(self.instruction, "task.instruction")
        if not isinstance(self.status, TaskStatus):
            raise DomainError("task.status must be a TaskStatus")

    def transition_to(self, status: TaskStatus) -> "Task":
        """Return a new task in the requested state if the transition is legal."""
        if not isinstance(status, TaskStatus) or status not in _ALLOWED_TRANSITIONS[self.status]:
            raise InvalidTransitionError(f"Cannot transition from {self.status} to {status}")
        return replace(self, status=status)
