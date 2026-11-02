"""Single-host, SQLite-backed immutable reports for the experimental evidence team.

The DB provides transactional task claims and explicit recovery. SHA-256 checks
detect accidental report corruption; they are not authentication or tamper-proof
security against an attacker who can change the database.
"""

import hashlib
import json
import sqlite3
from collections.abc import Callable, Sequence
from contextlib import closing
from dataclasses import asdict
from math import isfinite
from pathlib import Path
from typing import cast

from ares.runtime.evidence_risk import reconcile
from ares.runtime.evidence_team import (
    EvidenceTeamResult,
    GovernedEvidenceTeam,
    ReviewedRole,
)
from ares.runtime.temporal_evidence import EvidenceReading


class EvidenceTaskConflict(ValueError):
    """Existing task cannot safely be replayed with different arguments."""


def _fingerprint(readings: Sequence[EvidenceReading], identity: str) -> str:
    if not identity.strip() or len(identity) > 120:
        raise ValueError("team identity must be 1..120 nonblank characters")
    entries: list[list[object]] = []
    for item in readings:
        # Non-finite values are symbolic to preserve input identity without NaN JSON.
        temperature: object = (
            item.temperature_c
            if isfinite(item.temperature_c)
            else "nan"
            if item.temperature_c != item.temperature_c
            else "positive_inf"
            if item.temperature_c > 0
            else "negative_inf"
        )
        entries.append([item.step, temperature, item.healthy])
    payload = json.dumps(
        {"contract": "evidence-team-v1", "identity": identity, "readings": entries},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _decode_report(encoded: str, digest: str) -> EvidenceTeamResult:
    if hashlib.sha256(encoded.encode("utf-8")).hexdigest() != digest:
        raise ValueError("stored evidence report checksum mismatch")
    raw: object = json.loads(encoded)
    if not isinstance(raw, dict):
        raise ValueError("stored evidence report malformed")
    data = cast("dict[str, object]", raw)
    allowed = {
        "severity",
        "evidence_state",
        "authorized_action",
        "roles",
        "team_accepted",
        "device_actions",
        "safety_authority",
    }
    if set(data) != allowed:
        raise ValueError("stored evidence report fields malformed")
    roles = data["roles"]
    if not isinstance(roles, list):
        raise ValueError("stored evidence report roles malformed")
    checked_roles = cast("list[object]", roles)
    if len(checked_roles) != 3:
        raise ValueError("stored evidence report roles malformed")
    entries: list[ReviewedRole] = []
    for role in checked_roles:
        if not isinstance(role, dict):
            raise ValueError("stored evidence role malformed")
        fields = cast("dict[str, object]", role)
        if set(fields) != {"role", "proposed", "expected", "accepted", "diagnostic"}:
            raise ValueError("stored evidence role fields malformed")
        if any(type(fields[k]) is not str for k in ("role", "proposed", "expected", "diagnostic")):
            raise ValueError("stored evidence role type malformed")
        if type(fields["accepted"]) is not bool:
            raise ValueError("stored evidence role accepted malformed")
        entries.append(
            ReviewedRole(
                cast("str", fields["role"]),
                cast("str", fields["proposed"]),
                cast("str", fields["expected"]),
                fields["accepted"],
                cast("str", fields["diagnostic"]),
            )
        )
    if [role.role for role in entries] != ["investigator", "planner", "critic"]:
        raise ValueError("stored role order malformed")
    if any(
        type(data[k]) is not str
        for k in (
            "severity",
            "evidence_state",
            "authorized_action",
            "device_actions",
            "safety_authority",
        )
    ):
        raise ValueError("stored evidence header malformed")
    if (
        data["device_actions"] != "disabled"
        or data["safety_authority"] != "deterministic_evidence_risk"
    ):
        raise ValueError("stored report cannot contain executable authority")
    if type(data["team_accepted"]) is not bool:
        raise ValueError("stored team acceptance malformed")
    if data["severity"] not in ("normal", "warning", "critical"):
        raise ValueError("stored risk severity invalid")
    if data["evidence_state"] not in (
        "invalid_telemetry", "insufficient_history",
        "rising_temperature", "no_confirmed_rise",
    ):
        raise ValueError("stored evidence state invalid")
    if data["authorized_action"] not in (
        "monitor", "collect_evidence", "inspect", "validate_sensor", "human_review",
    ):
        raise ValueError("stored risk action invalid")
    expected_by_role = (
        {"validate_sensor", "collect_more_samples", "inspect_thermal_system", "continue_monitoring"},
        {"monitor", "collect_evidence", "inspect", "validate_sensor", "human_review"},
        {"consistent", "inconsistent"},
    )
    diagnostic_codes = {
        "accepted", "policy_mismatch", "oversized_response",
        "invalid_json", "invalid_shape", "invalid_fields",
        "invalid_value", "model_exception",
    }
    for item, allowed_values in zip(entries, expected_by_role, strict=True):
        if item.expected not in allowed_values:
            raise ValueError("stored expected role category invalid")
        if item.proposed not in allowed_values and item.proposed != "unrecognized":
            raise ValueError("stored proposed role category invalid")
        if item.diagnostic not in diagnostic_codes:
            raise ValueError("stored role diagnostic invalid")
        if item.accepted != (item.proposed == item.expected and item.diagnostic == "accepted"):
            raise ValueError("stored role acceptance inconsistent")
    if data["team_accepted"] != all(item.accepted for item in entries):
        raise ValueError("stored team acceptance inconsistent")
    expected_action = (
        "validate_sensor"
        if data["evidence_state"] == "invalid_telemetry"
        else "human_review"
        if data["severity"] == "critical"
        else "inspect"
        if data["severity"] == "warning" or data["evidence_state"] == "rising_temperature"
        else "collect_evidence"
        if data["evidence_state"] == "insufficient_history"
        else "monitor"
    )
    if data["authorized_action"] != expected_action:
        raise ValueError("stored action inconsistent with governed risk")
    return EvidenceTeamResult(
        cast("str", data["severity"]),
        cast("str", data["evidence_state"]),
        cast("str", data["authorized_action"]),
        tuple(entries),
        data["team_accepted"],
    )


class DurableEvidenceStore:
    """Local-only idempotent report store; does not run device commands."""

    def __init__(self, path: Path) -> None:
        if path.is_symlink():
            raise ValueError("database symlink not allowed")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with closing(sqlite3.connect(path, timeout=3)) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS evidence_tasks ("
                "task_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL, "
                "status TEXT NOT NULL, result TEXT, digest TEXT, attempts INTEGER NOT NULL)"
            )
            db.commit()

    def claim(
        self, task_id: str, request_hash: str, *, recover: bool = False
    ) -> EvidenceTeamResult | None:
        if not task_id.strip() or len(task_id) > 128:
            raise ValueError("task_id must be 1..128 nonblank characters")
        with closing(sqlite3.connect(self.path, timeout=3)) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT request_hash, status, result, digest, attempts "
                "FROM evidence_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if row is not None:
                previous_hash, status, result, digest, attempts = row
                if previous_hash != request_hash:
                    raise EvidenceTaskConflict("task id was used for a different request")
                if status == "completed":
                    if not isinstance(result, str) or not isinstance(digest, str):
                        raise ValueError("completed evidence task missing report")
                    return _decode_report(result, digest)
                if not recover or status == "running":
                    raise EvidenceTaskConflict("task unfinished; recovery requires failed status")
                if attempts >= 3:
                    raise EvidenceTaskConflict("evidence task recovery budget exhausted")
                db.execute(
                    "UPDATE evidence_tasks SET status = 'running', attempts = ? WHERE task_id = ?",
                    (attempts + 1, task_id),
                )
            else:
                db.execute(
                    "INSERT INTO evidence_tasks (task_id, request_hash, status, attempts) "
                    "VALUES (?, ?, 'running', 1)",
                    (task_id, request_hash),
                )
            db.commit()
        return None

    def complete(self, task_id: str, report: EvidenceTeamResult) -> None:
        encoded = json.dumps(asdict(report), sort_keys=True, allow_nan=False)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        _decode_report(encoded, digest)
        with closing(sqlite3.connect(self.path, timeout=3)) as db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute(
                "UPDATE evidence_tasks SET result = ?, digest = ?, status = 'completed' "
                "WHERE task_id = ? AND status = 'running'",
                (encoded, digest, task_id),
            )
            if cursor.rowcount != 1:
                raise EvidenceTaskConflict("evidence task not running")
            db.commit()

    def fail(self, task_id: str) -> None:
        with closing(sqlite3.connect(self.path, timeout=3)) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE evidence_tasks SET status = 'failed' "
                "WHERE task_id = ? AND status = 'running'",
                (task_id,),
            )
            db.commit()

    def completed(self, *, limit: int = 100) -> tuple[tuple[str, EvidenceTeamResult], ...]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be 1..1000")
        with closing(sqlite3.connect(self.path, timeout=3)) as db:
            rows = db.execute(
                "SELECT task_id, result, digest FROM evidence_tasks "
                "WHERE status = 'completed' ORDER BY task_id LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(
            (str(task_id), _decode_report(str(encoded), str(digest)))
            for task_id, encoded, digest in rows
        )


def run_durable_evidence_team(
    store: DurableEvidenceStore,
    generator: Callable[[str], str],
    readings: Sequence[EvidenceReading],
    *,
    task_id: str,
    identity: str,
    recover: bool = False,
) -> EvidenceTeamResult:
    """Run exactly once per task ID, with explicit failed-task recovery.

    A genuinely crashed process may leave a 'running' claim that requires
    an operator-controlled procedure; it is never silently resumed.
    """
    # Validate input before acquiring a claim.
    reconcile(readings)
    fingerprint = _fingerprint(readings, identity)
    existing = store.claim(task_id, fingerprint, recover=recover)
    if existing is not None:
        return existing
    try:
        report = GovernedEvidenceTeam(generator).evaluate(readings)
        if report.device_actions != "disabled":
            raise ValueError("team unexpectedly gained actuator authority")
        store.complete(task_id, report)
        return report
    except Exception:
        store.fail(task_id)
        raise
