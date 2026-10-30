"""End-to-end model proposal through an isolated local HTTP worker."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from ares.intelligence.decisions import DecisionKind, ProposalEngine
from ares.intelligence.ollama import OllamaAdapter
from ares.intelligence.ollama_preemptive import PreemptiveOllamaTransport
from ares.intelligence.transport import ProviderClient, RequestLimits
from ares.simulation import DeviceSnapshot
from ares.supervisor import Assessment, Severity


class OllamaStub(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        content = {
            "kind": "request_review",
            "rationale": "Request expert review",
            "assessment_severity": "critical",
        }
        output = json.dumps({"response": json.dumps(content)}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(output)))
        self.end_headers()
        self.wfile.write(output)

    def log_message(self, format: str, *args: object) -> None:
        pass


def test_preemptive_transport_full_proposal_roundtrip() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), OllamaStub)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        assert isinstance(port, int)
        transport = PreemptiveOllamaTransport(port=port)
        limits = RequestLimits(timeout_seconds=5.0)
        model = OllamaAdapter(ProviderClient(transport, limits), "stub-model")
        assessment = Assessment(
            DeviceSnapshot("sim", 1, 85.0, True),
            Severity.CRITICAL,
            "Critical simulated temperature",
            "Request engineer review",
        )
        decision = ProposalEngine(model).propose(assessment)
        assert decision.kind is DecisionKind.REQUEST_REVIEW
        assert decision.assessment_severity is Severity.CRITICAL
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
