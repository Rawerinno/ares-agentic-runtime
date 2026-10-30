"""Subprocess isolation enforces a wall-clock budget independently of urllib."""

from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from time import monotonic, sleep

import pytest

from ares.intelligence.ollama_preemptive import PreemptiveOllamaTransport
from ares.intelligence.transport import ProviderTransportError, RequestLimits


class Endpoint(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path == "/api/generate":
            sleep(1.5)
        payload = b"ok"
        self.send_response(200)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        with suppress(OSError):
            self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        pass


def test_preemptive_transport_terminates_slow_request() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Endpoint)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        assert isinstance(port, int)
        transport = PreemptiveOllamaTransport(port=port)
        started = monotonic()
        with pytest.raises(ProviderTransportError, match="deadline_exceeded"):
            transport.request(b"{}", limits=RequestLimits(timeout_seconds=0.4))
        assert monotonic() - started < 1.4
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_preemptive_transport_rejects_non_loopback() -> None:
    with pytest.raises(ValueError, match="loopback"):
        PreemptiveOllamaTransport(host="8.8.8.8")
