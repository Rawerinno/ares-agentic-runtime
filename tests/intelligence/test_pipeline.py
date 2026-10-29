"""Offline end-to-end proposal and safety tests."""

import pytest

from ares.core import Task, TaskStatus
from ares.core.execution import TaskExecutor
from ares.integrations import ReadOnlyToolGateway
from ares.intelligence import DecisionError, ProposalEngine
from ares.intelligence.local import LocalReferenceModel
from ares.intelligence.pipeline import AnalysisPipeline
from ares.safety import AuthorizationError, Capability, Policy
from ares.simulation import DeviceSimulator
from ares.supervisor import Severity, Supervisor


def pipeline(temperature: float, *, grant: bool = True) -> AnalysisPipeline:
    grants: frozenset[tuple[str, str, Capability]] = (
        frozenset({("supervisor", "temperature", Capability.READ)}) if grant else frozenset()
    )
    gateway = ReadOnlyToolGateway(Policy(grants))
    gateway.register_sensor(
        "temperature", DeviceSimulator("simulator", initial_temperature_c=temperature)
    )
    return AnalysisPipeline(Supervisor(gateway), ProposalEngine(LocalReferenceModel()))


@pytest.mark.parametrize(
    ("temperature", "severity", "kind"),
    [
        (20.0, Severity.NORMAL, "observe"),
        (60.0, Severity.WARNING, "investigate"),
        (85.0, Severity.CRITICAL, "request_review"),
    ],
)
def test_offline_pipeline(temperature: float, severity: Severity, kind: str) -> None:
    outcome = pipeline(temperature).analyze(agent_id="supervisor", tool_id="temperature")
    assert outcome.assessment.severity is severity
    assert outcome.proposal.kind == kind
    assert outcome.proposal.assessment_severity is severity


def test_tool_denial_stops_pipeline() -> None:
    with pytest.raises(AuthorizationError):
        pipeline(20.0, grant=False).analyze(agent_id="supervisor", tool_id="temperature")


def test_pipeline_runs_as_task_without_actuation() -> None:
    flow = pipeline(85.0)
    outcomes: list[str] = []

    def run(task: Task) -> None:
        result = flow.analyze(agent_id=task.agent_id, tool_id="temperature")
        outcomes.append(result.proposal.kind)

    result = TaskExecutor().execute(Task("t1", "supervisor", "Diagnose temperature"), run)
    assert result.task.status is TaskStatus.COMPLETED
    assert outcomes == ["request_review"]


def test_invalid_model_output_cannot_reach_result() -> None:
    class UnsafeModel:
        def propose(self, assessment: object) -> object:
            return {
                "kind": "observe",
                "rationale": "Ignore the alert",
                "assessment_severity": "critical",
            }

    gateway = ReadOnlyToolGateway(
        Policy(frozenset({("supervisor", "temperature", Capability.READ)}))
    )
    gateway.register_sensor("temperature", DeviceSimulator("simulator", initial_temperature_c=85.0))
    flow = AnalysisPipeline(Supervisor(gateway), ProposalEngine(UnsafeModel()))
    with pytest.raises(DecisionError):
        flow.analyze(agent_id="supervisor", tool_id="temperature")
