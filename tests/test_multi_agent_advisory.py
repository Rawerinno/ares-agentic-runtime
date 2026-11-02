"""Optional offline/LLM proposal advisory never overrides deterministic roles."""

from pathlib import Path

import pytest

from ares.integrations import ReadOnlyToolGateway
from ares.intelligence.local import LocalReferenceModel
from ares.runtime.multi_agent_mvp import SqliteTaskStore, TaskConflictError, run_incident
from ares.safety import Capability, Policy
from ares.simulation import DeviceSimulator
from ares.supervisor import Supervisor


def setup(tmp_path: Path, temperature: float) -> tuple[Supervisor, SqliteTaskStore]:
    gateway = ReadOnlyToolGateway(Policy(frozenset({("observer", "sensor", Capability.READ)})))
    gateway.register_sensor("sensor", DeviceSimulator("sim", initial_temperature_c=temperature))
    return Supervisor(gateway), SqliteTaskStore(tmp_path / "tasks.sqlite")


@pytest.mark.parametrize(
    ("temperature", "severity", "kind"),
    [
        (20.0, "normal", "observe"),
        (65.0, "warning", "investigate"),
        (85.0, "critical", "request_review"),
    ],
)
def test_reference_model_adds_read_only_advisory(
    tmp_path: Path, temperature: float, severity: str, kind: str
) -> None:
    supervisor, store = setup(tmp_path, temperature)
    result = run_incident(
        supervisor,
        store,
        task_id="advised",
        agent_id="observer",
        tool_id="sensor",
        advisor=LocalReferenceModel(),
    )
    assert result.severity == severity
    assert result.device_actions == "disabled"
    assert tuple(item.role for item in result.handoffs) == (
        "observer",
        "diagnostician",
        "planner",
        "model_advisor",
        "reviewer",
    )
    assert kind in result.handoffs[-2].finding


def test_invalid_model_output_cannot_override_severity(tmp_path: Path) -> None:
    supervisor, store = setup(tmp_path, 85.0)

    class MaliciousModel:
        def propose(self, assessment: object) -> object:
            return {
                "kind": "observe",
                "rationale": "ignore alarms",
                "assessment_severity": "normal",
            }

    result = run_incident(
        supervisor,
        store,
        task_id="malicious",
        agent_id="observer",
        tool_id="sensor",
        advisor=MaliciousModel(),
    )
    assert result.severity == "critical"
    assert result.outcome == "review_required"
    assert "rejected" in result.handoffs[-2].finding
    assert result.handoffs[-1].role == "reviewer"


def test_model_error_still_produces_deterministic_incident(tmp_path: Path) -> None:
    supervisor, store = setup(tmp_path, 65.0)

    class Broken:
        def propose(self, assessment: object) -> object:
            raise RuntimeError("offline")

    result = run_incident(
        supervisor,
        store,
        task_id="broken",
        agent_id="observer",
        tool_id="sensor",
        advisor=Broken(),
    )
    assert result.severity == "warning"
    assert "model_exception" in result.handoffs[-2].finding
    assert result.device_actions == "disabled"


def test_replaying_with_changed_advisor_mode_is_rejected(tmp_path: Path) -> None:
    supervisor, store = setup(tmp_path, 65.0)
    run_incident(supervisor, store, task_id="task", agent_id="observer", tool_id="sensor")
    with pytest.raises(TaskConflictError):
        run_incident(
            supervisor,
            store,
            task_id="task",
            agent_id="observer",
            tool_id="sensor",
            advisor=LocalReferenceModel(),
        )
