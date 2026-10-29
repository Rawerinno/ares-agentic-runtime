"""Local-only Ollama transport with bounded reads and a real socket timeout."""

import ipaddress
from urllib.error import HTTPError, URLError
from urllib.request import HTTPHandler, HTTPRedirectHandler, Request, build_opener

from ares.intelligence.transport import ProviderTransportError, RequestLimits


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req: Request, fp: object, code: int, msg: str, headers: object, newurl: str) -> None:
        return None


class OllamaLocalTransport:
    """Connect only to a literal loopback address, never follow redirects."""

    def __init__(self, port: int = 11434, host: str = "127.0.0.1") -> None:
        try:
            address = ipaddress.ip_address(host)
        except ValueError as exc:
            raise ValueError("Ollama host must be a numeric loopback IP") from exc
        if not address.is_loopback:
            raise ValueError("Ollama must be hosted on loopback")
        if not 1 <= port <= 65535:
            raise ValueError("Invalid Ollama port")
        netloc = f"[{address}]" if address.version == 6 else str(address)
        self._url = f"http://{netloc}:{port}/api/generate"
        self._opener = build_opener(HTTPHandler(), _RejectRedirects())

    def request(self, payload: bytes, *, limits: RequestLimits) -> bytes:
        """Apply socket timeout and enforce a cap while reading response bytes.

        urllib's timeout is a socket-operation timeout, not an absolute
        end-to-end deadline; use only with trusted local Ollama processes.
        """
        req = Request(
            self._url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener.open(req, timeout=limits.timeout_seconds) as response:
                if response.status != 200:
                    raise ProviderTransportError("ollama_http_error")
                content = response.read(limits.max_response_bytes + 1)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise ProviderTransportError("ollama_connection_failed") from exc
        if len(content) > limits.max_response_bytes:
            raise ProviderTransportError("provider_response_too_large")
        return content
