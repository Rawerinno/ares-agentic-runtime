"""Offline Ollama adapter contract tests; no Ollama installation needed."""

import json

import pytest

from ares.intelligence.decisions import ProposalEngine
from ares.intelligence.ollama import OllamaAdapter
from ares.intelligence.ollama_transport import OllamaLocalTransport
from ares.intelligence.transport import ProviderClient, RequestLimits
from ares.simulation import DeviceSnapshot
from ares.supervisor import Assessment, Severity


class FakeTransport:
    def __init__(self, response: bytes) -> None:
        self.response = response
        self.payload: bytes = b""

    def request(self, payload: bytes, *, limits: RequestLimits) -> bytes:
        self.payload = payload
        return self.response


def assessment(severity: Severity = Severity.CRITICAL) -> Assessment:
    return Assessment(DeviceSnapshot("sensor", 0, 86.0, True), severity, "Hot", "Review")


def make_adapter(transport: FakeTransport) -> OllamaAdapter:
    return OllamaAdapter(ProviderClient(transport, RequestLimits()), "example-model")


def test_structured_ollama_response_and_request() -> None:
    decision = {
        "kind": "request_review",
        "rationale": "Engineer must review overheating",
        "assessment_severity": "critical",
    }
    transport = FakeTransport(json.dumps({"response": json.dumps(decision)}).encode())
    result = ProposalEngine(make_adapter(transport)).propose(assessment())
    assert result.kind == "request_review"
    request = json.loads(transport.payload)
    assert request["model"] == "example-model"
    assert request["stream"] is False
    assert request["format"]["additionalProperties"] is False
    assert request["options"]["num_predict"] == 256
    assert "86.0" in request["prompt"]


@pytest.mark.parametrize("value", [b"bad", b"[]", b'{"response": 4}', b"{}"])
def test_malformed_envelopes_rejected(value: bytes) -> None:
    with pytest.raises(ValueError, match="ollama_invalid_response"):
        make_adapter(FakeTransport(value)).propose(assessment())


def test_model_cannot_override_critical_review() -> None:
    unsafe = {
        "kind": "observe",
        "rationale": "Ignore",
        "assessment_severity": "critical",
    }
    transport = FakeTransport(json.dumps({"response": json.dumps(unsafe)}).encode())
    with pytest.raises(ValueError):
        ProposalEngine(make_adapter(transport)).propose(assessment())


def test_transport_host_restriction() -> None:
    OllamaLocalTransport()
    OllamaLocalTransport(host="::1")
    for host in ("ollama.local", "8.8.8.8", "192.168.1.2"):
        with pytest.raises(ValueError):
            OllamaLocalTransport(host=host)


def test_invalid_model_and_port() -> None:
    with pytest.raises(ValueError):
        make_adapter(FakeTransport(b"{}")).__class__(
            ProviderClient(FakeTransport(b"{}"), RequestLimits()), " "
        )
    with pytest.raises(ValueError):
        OllamaLocalTransport(port=0)
