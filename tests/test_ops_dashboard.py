"""Offline operations dashboard tests and escaping guarantees."""

from pathlib import Path

import pytest
from pytest import CaptureFixture

from ares.integrations import ReadOnlyToolGateway
from ares.runtime.dashboard import render_dashboard, run
from ares.runtime.multi_agent_mvp import (
    IncidentReport,
    RoleHandoff,
    SqliteTaskStore,
    run_incident,
)
from ares.safety import Capability, Policy
from ares.simulation import DeviceSimulator
from ares.supervisor import Supervisor


def test_dashboard_escapes_untrusted_stored_strings() -> None:
    report = IncidentReport(
        task_id='<script>alert("x")</script>',
        device_id='sensor"onload="bad',
        observed_step=0,
        temperature_c=80,
        severity="critical",
        outcome="review_required",
        handoffs=(RoleHandoff("advisor", "<img src=x>", 'bad & "unsafe"'),),
    )
    page = render_dashboard((report,), {"completed": 1})
    assert "<script>alert" not in page
    assert "<img src=x>" not in page
    assert "&lt;script&gt;" in page
    assert "&lt;img src=x&gt;" in page
    assert "unsafe&quot;" in page
    assert "default-src 'none'" in page


def test_empty_dashboard_has_no_completed_incidents() -> None:
    page = render_dashboard((), {"failed": 2, "running": 1})
    assert "No completed incidents" in page
    assert "Failed tasks" in page
    assert "Unfinished tasks" in page


def test_export_read_only_tasks_and_handoffs(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db = tmp_path / "store.sqlite"
    store = SqliteTaskStore(db)
    device = DeviceSimulator("sim", initial_temperature_c=85)
    gateway = ReadOnlyToolGateway(Policy(frozenset({("observer", "sensor", Capability.READ)})))
    gateway.register_sensor("sensor", device)
    run_incident(
        Supervisor(gateway), store, task_id="critical-01",
        agent_id="observer", tool_id="sensor",
    )
    output = tmp_path / "ops.html"
    assert run(["--db", str(db), "--output", str(output)]) == 0
    assert "created" in capsys.readouterr().out
    content = output.read_text(encoding="utf-8")
    assert "critical-01" in content
    assert "review_required" in content
    assert "diagnostician" in content
    assert "reviewer" in content
    assert store.summary() == {"completed": 1}


def test_report_limit_is_bounded(tmp_path: Path) -> None:
    store = SqliteTaskStore(tmp_path / "store.sqlite")
    with pytest.raises(ValueError):
        store.completed_reports(limit=0)
    with pytest.raises(ValueError):
        store.completed_reports(limit=1001)
