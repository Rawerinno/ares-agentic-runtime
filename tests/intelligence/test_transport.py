"""Transport contract tests without network or secrets."""

import pytest

from ares.intelligence.transport import (
    ProviderClient,
    ProviderTransportError,
    RequestLimits,
)


class FakeTransport:
    def __init__(self, response: object) -> None:
        self.response = response
        self.seen_limits: RequestLimits | None = None

    def request(self, payload: bytes, *, limits: RequestLimits) -> bytes:
        self.seen_limits = limits
        if isinstance(self.response, Exception):
            raise self.response
        if not isinstance(self.response, bytes):
            return self.response  # type: ignore[return-value]
        return self.response


def test_success_and_limit_forwarding() -> None:
    limits = RequestLimits(timeout_seconds=2, max_response_bytes=8)
    transport = FakeTransport(b"ok")
    assert ProviderClient(transport, limits).request(b"ping") == b"ok"
    assert transport.seen_limits == limits


def test_oversized_response_rejected() -> None:
    with pytest.raises(ProviderTransportError, match="provider_response_too_large"):
        ProviderClient(FakeTransport(b"long"), RequestLimits(max_response_bytes=2)).request(
            b"ping"
        )


def test_unexpected_response_type_rejected() -> None:
    with pytest.raises(ProviderTransportError, match="invalid_transport_response"):
        ProviderClient(FakeTransport("unexpected"), RequestLimits()).request(b"ping")


def test_transport_errors_are_redacted() -> None:
    with pytest.raises(ProviderTransportError, match="provider_transport_failed"):
        ProviderClient(
            FakeTransport(RuntimeError("sensitive credential")),
            RequestLimits(),
        ).request(b"ping")


@pytest.mark.parametrize(
    ("timeout", "max_bytes"),
    [(0.0, 1), (-1.0, 1), (float("nan"), 1), (float("inf"), 1), (1.0, 0)],
)
def test_invalid_limits(timeout: float, max_bytes: int) -> None:
    with pytest.raises(ValueError):
        RequestLimits(timeout_seconds=timeout, max_response_bytes=max_bytes)
