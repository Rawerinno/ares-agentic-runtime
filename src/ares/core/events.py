"""Immutable records of task lifecycle events."""

from dataclasses import dataclass
from enum import StrEnum

from ares.core.errors import DomainError
from ares.core.models import _require_text


class EventKind(StrEnum):
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"


@dataclass(frozen=True, slots=True)
class Event:
    """An auditable observation linked to a task."""

    id: str
    task_id: str
    kind: EventKind
    detail: str = ""

    def __post_init__(self) -> None:
        _require_text(self.id, "event.id")
        _require_text(self.task_id, "event.task_id")
        if not isinstance(self.kind, EventKind):
            raise DomainError("event.kind must be an EventKind")
