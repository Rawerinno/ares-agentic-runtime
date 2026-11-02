"""Invalid simulated sensor readings always produce a persisted critical incident."""

from math import inf, nan
from pathlib import Path

import pytest

from ares.integrations import ReadOnlyToolGateway
from ares.runtime.dashboard import render_dashboard
from ares.runtime.multi_agent_mvp import SqliteTaskStore, run_incident
from ares.safety import Capability, Policy
from ares.simulation import DeviceSimulator
from ares.supervisor import Supervisor


@pytest.mark.parametrize("invalid", [nan, inf, -inf])
def test_nonfinite_sensor_is_persisted_as_critical(tmp_path: Path, invalid: float) -> None:
    gateway = ReadOnlyToolGateway(Policy(frozenset({("observer", "sensor", Capability.READ)})))
    gateway.register_sensor(
        "sensor", DeviceSimulator("invalid-sensor", initial_temperature_c=invalid)
    )
    supervisor = Supervisor(gateway)
    store = SqliteTaskStore(tmp_path / "tasks.sqlite")
    report = run_incident(
        supervisor,
        store,
        task_id="invalid-reading",
        agent_id="observer",
        tool_id="sensor",
    )
    assert report.severity == "critical"
    assert report.outcome == "review_required"
    assert report.temperature_c is None
    assert report.device_actions == "disabled"
    restored = SqliteTaskStore(tmp_path / "tasks.sqlite").completed_reports()
    assert restored == (report,)
    page = render_dashboard(restored, store.summary())
    assert "Unavailable" in page
    assert "review_required" in page
