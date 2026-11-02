"""Durable local evidence-team audit, replay and fail-closed DB persistence."""

import json
import sqlite3
from pathlib import Path

import pytest

from ares.runtime.evidence_team import evidence_team_reference_generate
from ares.runtime.evidence_team_store import (
    DurableEvidenceStore,
    EvidenceTaskConflict,
    run_durable_evidence_team,
)
from ares.runtime.temporal_evidence import EvidenceReading


def trace(*temps: float) -> tuple[EvidenceReading, ...]:
    return tuple(EvidenceReading(i, t) for i, t in enumerate(temps))


def test_replay_across_store_instances_does_not_repeat_model_calls(tmp_path: Path) -> None:
    location = tmp_path / "audit.sqlite"
    store = DurableEvidenceStore(location)
    calls: list[str] = []

    def generator(prompt: str) -> str:
        calls.append(prompt)
        return evidence_team_reference_generate(prompt)

    first = run_durable_evidence_team(
        store, generator, trace(85, 80, 75), task_id="case-1", identity="baseline-v1"
    )
    assert first.severity == "critical"
    assert first.authorized_action == "human_review"
    assert first.team_accepted
    assert len(calls) == 3
    second = run_durable_evidence_team(
        DurableEvidenceStore(location),
        generator,
        trace(85, 80, 75),
        task_id="case-1",
        identity="baseline-v1",
    )
    assert second == first
    assert len(calls) == 3
    assert store.completed() == (("case-1", first),)


def test_task_identity_binds_readings_and_model_identity(tmp_path: Path) -> None:
    store = DurableEvidenceStore(tmp_path / "audit.sqlite")
    run_durable_evidence_team(
        store, evidence_team_reference_generate, trace(60), task_id="case", identity="model-1"
    )
    with pytest.raises(EvidenceTaskConflict):
        run_durable_evidence_team(
            store, evidence_team_reference_generate, trace(65), task_id="case",
            identity="model-1",
        )
    with pytest.raises(EvidenceTaskConflict):
        run_durable_evidence_team(
            store, evidence_team_reference_generate, trace(60), task_id="case",
            identity="model-2",
        )


def test_failed_task_requires_explicit_recovery(tmp_path: Path) -> None:
    store = DurableEvidenceStore(tmp_path / "audit.sqlite")

    def bad(_prompt: str) -> str:
        # Untrusted model errors are handled by the team; not a workflow failure.
        raise RuntimeError("provider token")

    result = run_durable_evidence_team(
        store, bad, trace(85), task_id="case", identity="model-1"
    )
    assert not result.team_accepted
    assert all(role.diagnostic == "model_exception" for role in result.roles)
    assert "provider token" not in json.dumps(store.completed(), default=str)
    assert run_durable_evidence_team(
        store, evidence_team_reference_generate, trace(85), task_id="case",
        identity="model-1",
    ) == result


def test_unfinished_claim_cannot_be_stolen_even_with_recover(tmp_path: Path) -> None:
    store = DurableEvidenceStore(tmp_path / "audit.sqlite")
    assert store.claim("pending", "request") is None
    with pytest.raises(EvidenceTaskConflict):
        store.claim("pending", "request")
    with pytest.raises(EvidenceTaskConflict):
        store.claim("pending", "request", recover=True)
    store.fail("pending")
    assert store.claim("pending", "request", recover=True) is None
    store.fail("pending")
    assert store.claim("pending", "request", recover=True) is None
    store.fail("pending")
    with pytest.raises(EvidenceTaskConflict):
        store.claim("pending", "request", recover=True)


def test_corrupt_report_is_detected_and_never_replayed(tmp_path: Path) -> None:
    location = tmp_path / "audit.sqlite"
    store = DurableEvidenceStore(location)
    run_durable_evidence_team(
        store, evidence_team_reference_generate, trace(85), task_id="case",
        identity="model-1",
    )
    with sqlite3.connect(location) as db:
        db.execute(
            "UPDATE evidence_tasks SET result = ? WHERE task_id = ?",
            ('{"untrusted":"corruption"}', "case"),
        )
    with pytest.raises(ValueError, match="checksum"):
        store.completed()


def test_nonfinite_input_has_stable_identity_without_nan_json(tmp_path: Path) -> None:
    store = DurableEvidenceStore(tmp_path / "audit.sqlite")
    result = run_durable_evidence_team(
        store,
        evidence_team_reference_generate,
        trace(20, float("nan")),
        task_id="nonfinite",
        identity="baseline-v1",
    )
    assert result.severity == "critical"
    assert result.authorized_action == "validate_sensor"
    assert result == run_durable_evidence_team(
        store,
        evidence_team_reference_generate,
        trace(20, float("nan")),
        task_id="nonfinite",
        identity="baseline-v1",
    )


def test_invalid_or_symlink_db_and_inputs_are_rejected(tmp_path: Path) -> None:
    target = tmp_path / "real.sqlite"
    DurableEvidenceStore(target)
    link = tmp_path / "alias.sqlite"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        DurableEvidenceStore(link)
    store = DurableEvidenceStore(target)
    with pytest.raises(ValueError):
        run_durable_evidence_team(
            store, evidence_team_reference_generate, (), task_id="bad", identity="model-1"
        )
    with pytest.raises(ValueError):
        run_durable_evidence_team(
            store, evidence_team_reference_generate, trace(20), task_id="bad",
            identity="",
        )
    with pytest.raises(ValueError):
        run_durable_evidence_team(
            store, evidence_team_reference_generate, trace(20), task_id="", identity="model-1"
        )
    assert store.completed() == ()


def test_malformed_role_fields_refused_even_with_matching_checksum(tmp_path: Path) -> None:
    import hashlib

    store = DurableEvidenceStore(tmp_path / "audit.sqlite")
    run_durable_evidence_team(
        store, evidence_team_reference_generate, trace(60), task_id="case",
        identity="model-1",
    )
    with sqlite3.connect(store.path) as db:
        report = json.loads(
            db.execute("SELECT result FROM evidence_tasks WHERE task_id = 'case'").fetchone()[0]
        )
        report["device_actions"] = "enabled"
        encoded = json.dumps(report, sort_keys=True)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        db.execute(
            "UPDATE evidence_tasks SET result = ?, digest = ? WHERE task_id = 'case'",
            (encoded, digest),
        )
    with pytest.raises(ValueError, match="authority"):
        store.completed()
