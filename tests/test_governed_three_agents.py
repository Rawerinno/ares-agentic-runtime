"""Three separate simulated LLM invocations remain under deterministic policy."""

import json
from pathlib import Path

import pytest
from pytest import CaptureFixture, MonkeyPatch

from ares.integrations import ReadOnlyToolGateway
from ares.runtime import demo
from ares.runtime.governed_three_agents import GovernedThreeAgentTeam
from ares.runtime.multi_agent_mvp import SqliteTaskStore, TaskConflictError, run_incident
from ares.safety import Capability, Policy
from ares.simulation import DeviceSimulator
from ares.supervisor import Supervisor


def setup(tmp_path: Path, temperature: float) -> tuple[Supervisor, SqliteTaskStore]:
    gateway = ReadOnlyToolGateway(Policy(frozenset({("observer", "sensor", Capability.READ)})))
    gateway.register_sensor("sensor", DeviceSimulator("device", initial_temperature_c=temperature))
    return Supervisor(gateway), SqliteTaskStore(tmp_path / "jobs.sqlite")


def generator(prompt: str) -> str:
    role = prompt.split("ROLE=", 1)[1].split(".", 1)[0]
    raw = json.loads(prompt.split("Trusted context: ", 1)[1].removesuffix("."))
    severity = raw["severity"]
    if role == "investigator":
        hypothesis = "stable" if severity == "normal" else "thermal_load"
        return json.dumps({"hypothesis": hypothesis, "severity": severity})
    if role == "planner":
        plan = {"normal": "monitor", "warning": "inspect", "critical": "human_review"}[severity]
        return json.dumps({"plan": plan, "severity": severity})
    if role == "critic":
        return json.dumps({"verdict": "consistent", "severity": severity})
    raise ValueError("unsupported role")


@pytest.mark.parametrize(
    "temperature,severity", [(20.0, "normal"), (65.0, "warning"), (85.0, "critical")]
)
def test_three_distinct_model_invocations_have_no_tool_authority(
    tmp_path: Path, temperature: float, severity: str
) -> None:
    supervisor, store = setup(tmp_path, temperature)
    prompts: list[str] = []

    def measured(prompt: str) -> str:
        prompts.append(prompt)
        return generator(prompt)

    team = GovernedThreeAgentTeam(measured, identity="team-v1")
    report = run_incident(
        supervisor, store, task_id="one", agent_id="observer", tool_id="sensor", team=team
    )
    assert report.severity == severity
    assert report.device_actions == "disabled"
    assert [handoff.role for handoff in report.handoffs] == [
        "observer",
        "diagnostician",
        "planner",
        "investigator",
        "planner",
        "critic",
        "reviewer",
    ]
    assert len(prompts) == 3
    assert [
        name
        for name in ("investigator", "planner", "critic")
        if any(f"ROLE={name}" in prompt for prompt in prompts)
    ] == ["investigator", "planner", "critic"]
    assert all("Validated" in h.finding for h in report.handoffs[3:6])
    assert (
        run_incident(
            supervisor, store, task_id="one", agent_id="observer", tool_id="sensor", team=team
        )
        == report
    )
    assert len(prompts) == 3


@pytest.mark.parametrize(
    "bad_role,bad_response,calls",
    [
        ("investigator", '{"hypothesis":"stable","severity":"warning"}', 1),
        ("planner", '{"plan":"monitor","severity":"warning"}', 2),
        ("critic", '{"verdict":"inconsistent","severity":"warning"}', 3),
    ],
)
def test_invalid_model_role_fails_closed_without_affecting_criticality(
    tmp_path: Path, bad_role: str, bad_response: str, calls: int
) -> None:
    supervisor, store = setup(tmp_path, 65)
    prompts: list[str] = []

    def malicious(prompt: str) -> str:
        prompts.append(prompt)
        if f"ROLE={bad_role}." in prompt:
            return bad_response
        return generator(prompt)

    team = GovernedThreeAgentTeam(malicious, identity="malicious-v1")
    report = run_incident(
        supervisor,
        store,
        task_id="malicious",
        agent_id="observer",
        tool_id="sensor",
        team=team,
    )
    assert report.severity == "warning"
    assert report.outcome == "investigation_recommended"
    assert report.device_actions == "disabled"
    assert len(prompts) == calls
    assert "Rejected" in report.handoffs[-2].finding
    assert report.handoffs[-1].role == "reviewer"


def test_model_error_does_not_override_critical_incident(tmp_path: Path) -> None:
    supervisor, store = setup(tmp_path, 85)

    def offline(_prompt: str) -> str:
        raise RuntimeError("sensitive credentials")

    report = run_incident(
        supervisor,
        store,
        task_id="offline",
        agent_id="observer",
        tool_id="sensor",
        team=GovernedThreeAgentTeam(offline),
    )
    assert report.severity == "critical"
    assert report.outcome == "review_required"
    assert "model_exception" in report.handoffs[-2].finding
    assert "sensitive credentials" not in str(report)
    assert store.summary() == {"completed": 1}


def test_team_identity_is_immutable_for_replay(tmp_path: Path) -> None:
    supervisor, store = setup(tmp_path, 20)
    run_incident(
        supervisor,
        store,
        task_id="identity",
        agent_id="observer",
        tool_id="sensor",
        team=GovernedThreeAgentTeam(generator, identity="model-A"),
    )
    with pytest.raises(TaskConflictError):
        run_incident(
            supervisor,
            store,
            task_id="identity",
            agent_id="observer",
            tool_id="sensor",
            team=GovernedThreeAgentTeam(generator, identity="model-B"),
        )


def test_cli_runs_three_offline_roles_without_ollama(
    tmp_path: Path, capsys: CaptureFixture[str], monkeypatch: MonkeyPatch
) -> None:
    def forbidden(_model: str) -> object:
        raise AssertionError("Ollama must not be invoked")

    monkeypatch.setattr(demo, "ollama_three_role_generator", forbidden)
    assert (
        demo.run(
            [
                "--temperature",
                "65",
                "--task-id",
                "demo-3",
                "--db",
                str(tmp_path / "tasks.sqlite"),
                "--team",
                "offline",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["team"] == "offline"
    assert [step["role"] for step in report["report"]["handoffs"]][-4:] == [
        "investigator",
        "planner",
        "critic",
        "reviewer",
    ]
