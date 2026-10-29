"""Contract tests for event records."""

from dataclasses import FrozenInstanceError

import pytest

from ares.core import DomainError, Event, EventKind


def test_event_records_task_activity() -> None:
    event = Event("e1", "t1", EventKind.TASK_STARTED, "Dispatch accepted")
    assert event.task_id == "t1"
    assert event.kind is EventKind.TASK_STARTED
    assert event.detail == "Dispatch accepted"


def test_event_detail_is_optional() -> None:
    event = Event("e2", "t1", EventKind.TASK_COMPLETED)
    assert event.detail == ""


@pytest.mark.parametrize("kind", list(EventKind))
def test_all_event_kinds_are_supported(kind: EventKind) -> None:
    assert Event("e1", "t1", kind).kind is kind


@pytest.mark.parametrize(
    ("event_id", "task_id"),
    [("", "t1"), (" ", "t1"), ("e1", ""), ("e1", " ")],
)
def test_event_requires_identifiers(event_id: str, task_id: str) -> None:
    with pytest.raises(DomainError):
        Event(event_id, task_id, EventKind.TASK_STARTED)


def test_event_rejects_unknown_kind() -> None:
    with pytest.raises(DomainError):
        Event("e1", "t1", "unknown")  # type: ignore[arg-type]


def test_event_is_immutable() -> None:
    event = Event("e1", "t1", EventKind.TASK_FAILED)
    with pytest.raises(FrozenInstanceError):
        event.detail = "changed"  # type: ignore[misc]
