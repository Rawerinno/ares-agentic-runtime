"""Provider transport contract with explicit deadline and output limits.

The transport implementation is injected. This module performs no network I/O.
"""

from dataclasses import dataclass
from typing import Protocol


class ProviderTransportError(RuntimeError):
    """A provider request could not be safely completed."""


@dataclass(frozen=True, slots=True)
class RequestLimits:
    timeout_seconds: float = 10.0
    max_response_bytes: int = 16384

    def __post_init__(self) -> None:
        from math import isfinite

        if not isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        if self.max_response_bytes < 1:
            raise ValueError("max_response_bytes must be positive")


class ProviderTransport(Protocol):
    """Implementation must enforce the supplied deadline while performing I/O."""

    def request(self, payload: bytes, *, limits: RequestLimits) -> bytes:
        """Return bounded response bytes or raise a transport error."""


class ProviderClient:
    """Validate transport output boundaries; never log response contents."""

    def __init__(self, transport: ProviderTransport, limits: RequestLimits) -> None:
        self._transport = transport
        self._limits = limits

    def request(self, payload: bytes) -> bytes:
        try:
            response = self._transport.request(payload, limits=self._limits)
        except Exception as exc:
            raise ProviderTransportError("provider_transport_failed") from exc
        if not isinstance(response, bytes):
            raise ProviderTransportError("invalid_transport_response")
        if len(response) > self._limits.max_response_bytes:
            raise ProviderTransportError("provider_response_too_large")
        return response
