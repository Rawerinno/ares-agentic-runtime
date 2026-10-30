"""Local HTTP transport: redirect, oversize and connection failure tests."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import ClassVar

import pytest

from ares.intelligence.ollama_transport import OllamaLocalTransport
from ares.intelligence.transport import ProviderTransportError, RequestLimits


class Handler(BaseHTTPRequestHandler):
    scenario: ClassVar[str] = "normal"

    def do_POST(self) -> None:
        body = b"ok"
        status = 200
        if self.scenario == "redirect":
            status = 302
            body = b"redirect"
        elif self.scenario == "oversize":
            body = b"x" * 65
        elif self.scenario == "http_error":
            status = 503
        self.send_response(status)
        if status == 302:
            self.send_header("Location", "http://example.invalid/")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("normal", None),
        ("redirect", "ollama_connection_failed"),
        ("oversize", "provider_response_too_large"),
        ("http_error", "ollama_connection_failed"),
    ],
)
def test_local_http_fail_closed(scenario: str, expected: str | None) -> None:
    class ScenarioHandler(Handler):
        pass

    ScenarioHandler.scenario = scenario
    server = ThreadingHTTPServer(("127.0.0.1", 0), ScenarioHandler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        port = server.server_address[1]
        assert isinstance(port, int)
        transport = OllamaLocalTransport(port=port)
        if expected is None:
            assert transport.request(b"{}", limits=RequestLimits(max_response_bytes=64)) == b"ok"
        else:
            with pytest.raises(ProviderTransportError, match=expected):
                transport.request(b"{}", limits=RequestLimits(max_response_bytes=64))
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()


def test_non_loopback_host_rejected() -> None:
    with pytest.raises(ValueError, match="loopback"):
        OllamaLocalTransport(host="8.8.8.8")
    with pytest.raises(ValueError, match="loopback"):
        OllamaLocalTransport(host="example.invalid")
