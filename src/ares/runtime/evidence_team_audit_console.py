"""Read-only local evidence-team audit inspection and integrity verification."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from ares.runtime.evidence_team_store import DurableEvidenceStore


def summarize(db_path: Path, *, limit: int = 1000) -> dict[str, object]:
    """Inspect existing task storage without creating it or invoking a model."""
    if not 1 <= limit <= 1000:
        raise ValueError("audit limit must be 1..1000")
    if not db_path.is_file() or db_path.is_symlink():
        raise ValueError("audit database must be an existing regular file")
    store = DurableEvidenceStore(db_path)
    counts = store.status_counts()
    reports = store.completed(limit=limit)
    total_completed = counts.get("completed", 0)
    verified = len(reports)
    return {
        "scope": "local_evidence_team_audit",
        "status_counts": counts,
        "completed_verified": verified,
        "complete_coverage": verified == total_completed,
        "truncated": total_completed > limit,
        "unresolved_tasks": counts.get("running", 0) + counts.get("failed", 0),
        "critical_incidents": sum(result.severity == "critical" for _, result in reports),
        "rejected_teams": sum(not result.team_accepted for _, result in reports),
        "device_actions": "disabled",
        "integrity": "sha256_plus_bounded_schema_not_signed_or_tamper_proof",
    }


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARES read-only evidence team audit console")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args(argv)
    try:
        report = summarize(args.db, limit=args.limit)
    except (ValueError, OSError) as exc:
        # Avoid echoing arbitrary database values or filesystem details.
        print(json.dumps({"scope": "local_evidence_team_audit", "error": type(exc).__name__}))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["complete_coverage"] and report["unresolved_tasks"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())
