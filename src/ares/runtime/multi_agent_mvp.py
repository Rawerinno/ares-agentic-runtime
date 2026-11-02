"""Durable, read-only multi-role incident workflow for simulated devices.

The workflow has explicit observer/diagnostician/planner/reviewer handoffs.
It is a deterministic MVP, NOT four autonomous LLM workers. No actuator
capabilities, network transports or unauthenticated human approvals exist.
"""

import hashlib
import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from math import isfinite
from pathlib import Path
from typing import cast

from ares.intelligence.decisions import ModelAdapter
from ares.intelligence.resilience import BoundedProposalEngine, OutcomeStatus
from ares.supervisor import Assessment, Severity, Supervisor


@dataclass(frozen=True, slots=True)
class RoleHandoff:
    role: str
    finding: str
    recommendation: str


@dataclass(frozen=True, slots=True)
class IncidentReport:
    task_id: str
    device_id: str
    observed_step: int
    temperature_c: float | None
    severity: str
    outcome: str
    handoffs: tuple[RoleHandoff, ...]
    device_actions: str = "disabled"


class TaskConflictError(ValueError):
    """Existing task has a different request or is actively running."""


def _request_hash(agent_id: str, tool_id: str, advisor_enabled: bool) -> str:
    payload = json.dumps([agent_id, tool_id, advisor_enabled], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class SqliteTaskStore:
    """Local single-host SQLite task state, atomic claims, and recovery.

    The operator must explicitly request recovery of an unfinished task.
    Completed tasks are immutable; replay returns their stored output without
    rereading devices or rerunning the roles. This does not implement a
    distributed lease, cross-host orchestration, or trusted multi-user access.
    """

    def __init__(self, path: Path) -> None:
        if path.is_symlink():
            raise ValueError("symlink task databases are forbidden")
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS tasks ("
                "task_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL, "
                "status TEXT NOT NULL, report_json TEXT, attempts INTEGER NOT NULL)"
            )

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection]:
        """Commit or roll back and always close the database handle."""
        db = sqlite3.connect(self._path, timeout=3)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _decode(payload: str) -> IncidentReport:
        raw: object = json.loads(payload)
        if not isinstance(raw, dict):
            raise ValueError("stored task report is malformed")
        fields = cast("dict[str, object]", raw)
        roles = fields["handoffs"]
        if not isinstance(roles, list):
            raise ValueError("stored role handoffs are malformed")
        handoffs: list[RoleHandoff] = []
        for item in cast("list[object]", roles):
            if not isinstance(item, dict):
                raise ValueError("stored role handoff is malformed")
            handoffs.append(RoleHandoff(**cast("dict[str, str]", item)))
        return IncidentReport(
            task_id=cast("str", fields["task_id"]),
            device_id=cast("str", fields["device_id"]),
            observed_step=cast("int", fields["observed_step"]),
            temperature_c=cast("float | None", fields["temperature_c"]),
            severity=cast("str", fields["severity"]),
            outcome=cast("str", fields["outcome"]),
            handoffs=tuple(handoffs),
            device_actions=cast("str", fields["device_actions"]),
        )

    def claim(
        self, task_id: str, request_hash: str, *, recover: bool = False
    ) -> IncidentReport | None:
        if not task_id.strip() or len(task_id) > 128:
            raise ValueError("task id must be 1..128 nonblank characters")
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT request_hash, status, report_json, attempts FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if row is not None:
                existing_hash, status, stored, attempts = row
                if existing_hash != request_hash:
                    raise TaskConflictError("task id belongs to a different request")
                if status == "completed":
                    if not isinstance(stored, str):
                        raise ValueError("completed task missing report")
                    return self._decode(stored)
                if not recover:
                    raise TaskConflictError("task unfinished; explicit recovery required")
                if attempts >= 3:
                    raise TaskConflictError("recovery budget exhausted")
                db.execute(
                    "UPDATE tasks SET status = 'running', attempts = ? WHERE task_id = ?",
                    (attempts + 1, task_id),
                )
            else:
                db.execute(
                    "INSERT INTO tasks (task_id, request_hash, status, attempts) "
                    "VALUES (?, ?, 'running', 1)",
                    (task_id, request_hash),
                )
        return None

    def complete(self, report: IncidentReport) -> None:
        encoded = json.dumps(asdict(report), sort_keys=True, allow_nan=False)
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute(
                "UPDATE tasks SET status = 'completed', report_json = ? "
                "WHERE task_id = ? AND status = 'running'",
                (encoded, report.task_id),
            )
            if cursor.rowcount != 1:
                raise TaskConflictError("task was not in running state")

    def mark_failed(self, task_id: str) -> None:
        with self._connection() as db:
            db.execute(
                "UPDATE tasks SET status = 'failed' WHERE task_id = ? AND status = 'running'",
                (task_id,),
            )

    def completed_reports(self, *, limit: int = 100) -> tuple[IncidentReport, ...]:
        """Read a bounded stable list of completed task outputs without mutation."""
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._connection() as db:
            rows = db.execute(
                "SELECT report_json FROM tasks WHERE status = 'completed' ORDER BY task_id LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(self._decode(str(payload)) for (payload,) in rows)

    def summary(self) -> dict[str, int]:
        with self._connection() as db:
            rows = db.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status").fetchall()
        return {str(status): int(count) for status, count in rows}


def _diagnose(assessment: Assessment) -> RoleHandoff:
    if assessment.severity is Severity.CRITICAL:
        return RoleHandoff(
            "diagnostician",
            "Critical thermal threshold reached",
            "Investigate thermal load and sensor validity immediately",
        )
    if assessment.severity is Severity.WARNING:
        return RoleHandoff(
            "diagnostician",
            "Temperature above warning threshold",
            "Review thermal trends and cooling capacity",
        )
    return RoleHandoff("diagnostician", "No threshold breach", "Continue observation")


def _plan(assessment: Assessment) -> RoleHandoff:
    if assessment.severity is Severity.CRITICAL:
        return RoleHandoff(
            "planner",
            "Human approval required for any corrective operation",
            "Escalate to engineer; do not actuate",
        )
    if assessment.severity is Severity.WARNING:
        return RoleHandoff("planner", "Inspection recommended", "Schedule manual investigation")
    return RoleHandoff("planner", "System observation normal", "Monitor without intervention")


def _review(assessment: Assessment, plan: RoleHandoff) -> RoleHandoff:
    if assessment.severity is Severity.CRITICAL and "do not actuate" not in plan.recommendation:
        raise ValueError("critical incident cannot bypass human review")
    return RoleHandoff(
        "reviewer",
        "Deterministic safety review passed",
        "No device operation authorized",
    )


def run_incident(
    supervisor: Supervisor,
    store: SqliteTaskStore,
    *,
    task_id: str,
    agent_id: str,
    tool_id: str,
    recover: bool = False,
    advisor: ModelAdapter | None = None,
) -> IncidentReport:
    """Run bounded roles, persist result, or mark failure for explicit retry."""
    previous = store.claim(
        task_id, _request_hash(agent_id, tool_id, advisor is not None), recover=recover
    )
    if previous is not None:
        return previous
    try:
        assessment = supervisor.assess(agent_id=agent_id, tool_id=tool_id)
        handoffs = (
            RoleHandoff("observer", assessment.reason, assessment.recommendation),
            _diagnose(assessment),
            _plan(assessment),
        )
        advice: tuple[RoleHandoff, ...] = ()
        if advisor is not None:
            outcome = BoundedProposalEngine(advisor).evaluate(assessment)
            if outcome.status is OutcomeStatus.ACCEPTED and outcome.decision is not None:
                advice = (
                    RoleHandoff(
                        "model_advisor",
                        f"Validated advisory kind: {outcome.decision.kind.value}",
                        "Model has no permission to execute device operations",
                    ),
                )
            else:
                advice = (
                    RoleHandoff(
                        "model_advisor",
                        f"Untrusted proposal rejected: {outcome.error_code}",
                        "Follow deterministic assessment; no model actuation",
                    ),
                )
        final = (*handoffs, *advice, _review(assessment, handoffs[-1]))
        report = IncidentReport(
            task_id=task_id,
            device_id=assessment.snapshot.device_id,
            observed_step=assessment.snapshot.step,
            temperature_c=(
                assessment.snapshot.temperature_c
                if isfinite(assessment.snapshot.temperature_c)
                else None
            ),
            severity=assessment.severity.value,
            outcome="review_required"
            if assessment.severity is Severity.CRITICAL
            else "investigation_recommended"
            if assessment.severity is Severity.WARNING
            else "observation_complete",
            handoffs=final,
        )
        store.complete(report)
        return report
    except Exception:
        store.mark_failed(task_id)
        raise
