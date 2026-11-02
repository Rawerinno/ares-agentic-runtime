"""Privacy-minimized audit records for bounded read-only agent collaboration."""

from ares.evaluation.audit import AuditEntry, append_entry
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ares.evaluation.bounded_team import BoundedTeamResult
    from ares.evaluation.concurrency_policy import SchedulingDecision


def record_bounded_execution(
    entries: tuple[AuditEntry, ...],
    report: "BoundedTeamResult",
    scheduling: "SchedulingDecision",
    *,
    call_count: int,
    elapsed_ms: float,
) -> tuple[AuditEntry, ...]:
    """Audit decision codes and metrics without storing sensor inputs or prompts."""
    if call_count < 0 or elapsed_ms < 0:
        raise ValueError("invalid bounded execution metrics")
    if report.status not in ("verified", "rejected"):
        raise ValueError("invalid bounded execution status")
    if report.status == "rejected" and report.severity is not None:
        raise ValueError("rejected result cannot authorize severity")
    if scheduling.parallelism not in (1, 2, 3):
        raise ValueError("invalid bounded execution parallelism")
    event: dict[str, object] = {
        "status": report.status,
        "severity": report.severity if report.status == "verified" else None,
        "error_codes": list(report.errors),
        "model_calls": call_count,
        "wall_time_ms": round(elapsed_ms, 2),
        "execution_mode": "parallel" if scheduling.parallelism > 1 else "sequential",
        "parallelism": scheduling.parallelism,
        "scheduler_reason": scheduling.reason,
        "model_authority": "advisory_only",
        "safety_authority": "deterministic_reviewer",
        "device_actions": "disabled",
    }
    return append_entry(entries, "bounded_team_completed", event)
