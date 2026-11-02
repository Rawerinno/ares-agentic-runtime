"""Role-only contracts and isolated evaluation without relaxed safety policy."""

import json
from pathlib import Path
from typing import cast

from pytest import MonkeyPatch

from ares.intelligence.transport import RequestLimits
from ares.runtime import three_agent_ollama
from ares.runtime.governed_three_agents import GovernedThreeAgentTeam, reference_generate
from ares.runtime.three_agent_acceptance import SCENARIOS, evaluate_three_roles
from ares.simulation import DeviceSnapshot
from ares.supervisor import Assessment, Severity


def scenario() -> Assessment:
    return Assessment(
        DeviceSnapshot("sim", 0, 65.0, True),
        Severity.WARNING,
        "warning",
        "investigate",
    )


def test_role_only_all_three_with_reference_and_no_severity_output() -> None:
    observed: list[str] = []

    def generator(prompt: str) -> str:
        value = reference_generate(prompt)
        observed.append(value)
        return value

    result = GovernedThreeAgentTeam(generator, role_only=True).evaluate(scenario())
    assert result.status == "accepted"
    assert result.calls == 3
    assert [set(cast("dict[str, str]", json.loads(value))) for value in observed] == [
        {"hypothesis"}, {"plan"}, {"verdict"}
    ]


def test_role_only_still_rejects_wrong_proposal() -> None:
    result = GovernedThreeAgentTeam(
        lambda _: '{"hypothesis":"stable"}', role_only=True
    ).evaluate(scenario())
    assert result.status == "rejected"
    assert result.error_code == "policy_mismatch"
    assert result.handoffs[-1].finding.endswith("hypothesis_mismatch")


def test_role_only_rejects_untrusted_severity_field_in_output() -> None:
    result = GovernedThreeAgentTeam(
        lambda _: '{"hypothesis":"thermal_load","severity":"warning"}',
        role_only=True,
    ).evaluate(scenario())
    assert result.status == "rejected"
    assert result.handoffs[-1].finding.endswith("invalid_fields")


def test_role_only_ollama_schema_requires_one_field(monkeypatch: MonkeyPatch) -> None:
    class RecordingTransport:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def request(self, payload: bytes, *, limits: RequestLimits) -> bytes:
            request = cast("dict[str, object]", json.loads(payload))
            self.calls.append(request)
            schema = cast("dict[str, object]", request["format"])
            required = cast("list[str]", schema["required"])
            assert len(required) == 1
            return json.dumps({"response": json.dumps({required[0]: "thermal_load"})}).encode()

    transport = RecordingTransport()
    monkeypatch.setattr(three_agent_ollama, "OllamaLocalTransport", lambda: transport)
    generate = three_agent_ollama.ollama_three_role_generator(
        "llama3.2:3b", role_only=True
    )
    assert json.loads(generate("ROLE=investigator. Trusted context: {}.")) == {
        "hypothesis": "thermal_load"
    }
    assert "severity" not in cast("dict[str, object]", transport.calls[0]["format"])[
        "required"
    ]


def test_isolated_probes_reach_downstream_roles_after_investigator_failure(
    tmp_path: Path,
) -> None:
    def generator(prompt: str) -> str:
        if "ROLE=investigator." in prompt:
            return json.dumps({"hypothesis": "stable"})
        return reference_generate(prompt)

    report = evaluate_three_roles(
        generator,
        tmp_path,
        repeats=1,
        scenarios=(SCENARIOS[4],),
        role_only=True,
        probe_roles=True,
    )
    assert report["governed_correct"] == 1
    assert report["full_team_accepted"] == 0
    probes = report["isolated_role_metrics"]
    assert isinstance(probes, dict)
    assert probes["investigator"]["attempted"] == 1
    assert probes["investigator"]["accepted"] == 0
    assert probes["planner"]["accepted"] == 1
    assert probes["critic"]["accepted"] == 1
    assert report["device_actions"] == "disabled"


def test_role_only_reference_acceptance_all_scenarios(tmp_path: Path) -> None:
    report = evaluate_three_roles(
        reference_generate, tmp_path, role_only=True, probe_roles=True, repeats=1
    )
    assert report["governed_correct"] == 9
    assert report["full_team_accepted"] == 9
    metrics = report["isolated_role_metrics"]
    assert isinstance(metrics, dict)
    assert all(metrics[role]["accepted"] == 9 for role in ("investigator", "planner", "critic"))
