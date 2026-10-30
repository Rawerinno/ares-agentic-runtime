"""Local HTTP transport: redirect, oversize and connection failure tests."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from time import sleep
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
        elif self.scenario == "partial":
            body = b"partial"
        self.send_response(status)
        if status == 302:
            self.send_header("Location", "http://example.invalid/")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.scenario == "delayed":
            sleep(0.15)
        if self.scenario == "partial":
            self.wfile.write(body[:2])
            self.wfile.flush()
            sleep(0.15)
            self.wfile.write(body[2:])
        else:
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
        ("partial", None),
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
            assert transport.request(b"{}", limits=RequestLimits(max_response_bytes=64)) == (
                b"partial" if scenario == "partial" else b"ok"
            )
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


def test_silent_body_exceeding_budget_rejected() -> None:
    class SlowHandler(Handler):
        scenario: ClassVar[str] = "delayed"

    server = ThreadingHTTPServer(("127.0.0.1", 0), SlowHandler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        port = server.server_address[1]
        assert isinstance(port, int)
        # Scheduling can exhaust the total deadline before the body read starts.
        # Both paths must fail closed; neither may return the delayed response.
        with pytest.raises(
            ProviderTransportError, match=r"^ollama_(connection_failed|deadline_exceeded)$"
        ):
            OllamaLocalTransport(port=port).request(
                b"{}", limits=RequestLimits(timeout_seconds=0.02)
            )
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()


def test_elapsed_budget_rejects_slow_partial_response() -> None:
    class SlowPartialHandler(Handler):
        scenario: ClassVar[str] = "partial"

    server = ThreadingHTTPServer(("127.0.0.1", 0), SlowPartialHandler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        port = server.server_address[1]
        assert isinstance(port, int)
        with pytest.raises(ProviderTransportError, match=r"deadline_exceeded|connection_failed"):
            OllamaLocalTransport(port=port).request(
                b"{}", limits=RequestLimits(timeout_seconds=0.1)
            )
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()
