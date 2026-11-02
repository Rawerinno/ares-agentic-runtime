"""Offline tests for the real role-specific Ollama transport contract."""

import json
from typing import cast

import pytest
from pytest import MonkeyPatch

from ares.intelligence.transport import RequestLimits
from ares.runtime import three_agent_ollama
from ares.runtime.governed_three_agents import GovernedThreeAgentTeam
from ares.simulation import DeviceSnapshot
from ares.supervisor import Assessment, Severity


class FakeTransport:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []
        self.override: object | None = None

    def request(self, payload: bytes, *, limits: RequestLimits) -> bytes:
        assert limits.max_response_bytes == 8192
        decoded: object = json.loads(payload)
        assert isinstance(decoded, dict)
        query = cast("dict[str, object]", decoded)
        self.requests.append(query)
        schema = query["format"]
        assert isinstance(schema, dict)
        fields = cast("dict[str, object]", schema)
        required = fields["required"]
        assert isinstance(required, list)
        key = cast("str", required[0])
        severity = "warning"
        content: object = {
            key: {"hypothesis": "thermal_load", "plan": "inspect", "verdict": "consistent"}[
                key
            ],
            "severity": severity,
        }
        if self.override is not None:
            content = self.override
        return json.dumps({"response": json.dumps(content)}).encode("utf-8")


def assessment() -> Assessment:
    return Assessment(
        DeviceSnapshot("sim", 0, 65.0, True),
        Severity.WARNING,
        "Warning sensor temperature",
        "Investigate thermal load",
    )


def test_three_realistic_ollama_json_objects_are_accepted(monkeypatch: MonkeyPatch) -> None:
    fake = FakeTransport()

    def factory() -> FakeTransport:
        return fake

    monkeypatch.setattr(three_agent_ollama, "OllamaLocalTransport", factory)
    generate = three_agent_ollama.ollama_three_role_generator("llama3.2:3b")
    outcome = GovernedThreeAgentTeam(generate).evaluate(assessment())
    assert outcome.status == "accepted"
    assert outcome.calls == 3
    assert len(fake.requests) == 3
    assert [cast("str", x["prompt"]).count("ROLE=") for x in fake.requests] == [1, 1, 1]
    assert all(x["stream"] is False and x["think"] is False for x in fake.requests)


@pytest.mark.parametrize(
    "reply",
    [
        {"hypothesis": "stable", "severity": "warning"},
        {"hypothesis": "thermal_load", "severity": "normal"},
        {"hypothesis": "thermal_load", "severity": "warning", "actuate": "on"},
        {"hypothesis": 1, "severity": "warning"},
        "not an object",
    ],
)
def test_untrusted_ollama_json_rejected_by_governor(
    monkeypatch: MonkeyPatch, reply: object
) -> None:
    fake = FakeTransport()
    fake.override = reply

    def factory() -> FakeTransport:
        return fake

    monkeypatch.setattr(three_agent_ollama, "OllamaLocalTransport", factory)
    outcome = GovernedThreeAgentTeam(
        three_agent_ollama.ollama_three_role_generator("llama3.2:3b")
    ).evaluate(assessment())
    assert outcome.status == "rejected"
    assert outcome.calls == 1


def test_bad_transport_response_is_model_error(monkeypatch: MonkeyPatch) -> None:
    class BrokenTransport:
        def request(self, payload: bytes, *, limits: RequestLimits) -> bytes:
            return b'{"response":123}'

    def factory() -> BrokenTransport:
        return BrokenTransport()

    monkeypatch.setattr(three_agent_ollama, "OllamaLocalTransport", factory)
    outcome = GovernedThreeAgentTeam(
        three_agent_ollama.ollama_three_role_generator("llama3.2:3b")
    ).evaluate(assessment())
    assert outcome.status == "rejected"
    assert outcome.error_code == "model_exception"
