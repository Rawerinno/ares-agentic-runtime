"""Offline loopback and deterministic socket fault tests; no hardware access."""

import json
import socket
from collections.abc import Callable, Generator
from contextlib import contextmanager
from threading import Thread
from time import monotonic, sleep
from unittest.mock import patch

import pytest

from ares.integrations.acquisition import BoundedAcquisition
from ares.integrations.acquisition_metrics import MonitoredAcquisition
from ares.integrations.tcp_readonly import ReadOnlyTCPTransport


def frame(step: int = 0, device: str = "sensor-1") -> bytes:
    return json.dumps(dict(device_id=device, step=step, temperature_c=22.5, healthy=True)).encode()


@contextmanager
def peer(*scripts: Callable[[socket.socket], None]) -> Generator[int]:
    errors: list[BaseException] = []
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(3)

        def serve() -> None:
            try:
                for script in scripts:
                    connection, _ = listener.accept()
                    with connection:
                        connection.settimeout(3)
                        script(connection)
            except BaseException as exc:
                errors.append(exc)

        worker = Thread(target=serve, daemon=True)
        worker.start()
        try:
            yield listener.getsockname()[1]
        finally:
            worker.join(4)
            assert not worker.is_alive(), "loopback peer did not finish"
            assert not errors, errors


def sends(payload: bytes) -> Callable[[socket.socket], None]:
    def send(connection: socket.socket) -> None:
        connection.sendall(payload)

    return send


def test_fragmented_coalesced_frames_and_no_application_writes() -> None:
    def script(connection: socket.socket) -> None:
        connection.sendall(frame()[:10])
        sleep(0.01)
        connection.sendall(frame()[10:] + b"\n" + frame(1) + b"\n")
        assert connection.recv(1) == b""  # client only closes, never sends payload

    with peer(script) as port:
        transport = ReadOnlyTCPTransport("127.0.0.1", port)
        assert transport.stats().connection_attempts == 0
        try:
            source = MonitoredAcquisition(BoundedAcquisition(transport.receive))
            assert source.read().snapshot is not None
            assert source.read().snapshot is not None
            assert source.stats().successful == 2
            stats = transport.stats()
            assert stats.frames == 2 and stats.connections == 1
            assert stats.bytes_received == len(frame()) + len(frame(1)) + 2
        finally:
            transport.close()
        assert not transport.stats().connected
        assert stats.connected  # immutable snapshot
        with pytest.raises(OSError, match="closed"):
            transport.receive(1)
        transport.close()


@pytest.mark.parametrize("payload", [b"\n", b"x" * 4097, b"partial"])
def test_invalid_framing_or_eof_disconnects(payload: bytes) -> None:
    with peer(sends(payload)) as port:
        transport = ReadOnlyTCPTransport("127.0.0.1", port)
        result = BoundedAcquisition(transport.receive).read()
        assert result.error_code == "acquisition_transport_error"
        assert not transport.stats().connected
        assert transport.stats().transport_errors == 1
        assert transport.stats().framing_errors == (0 if payload == b"partial" else 1)
        with pytest.raises(OSError, match="budget"):
            transport.receive(1)
        assert transport.stats().connection_attempts == 1


def test_maximum_frame_is_accepted() -> None:
    with peer(sends(b"x" * 4096 + b"\n")) as port:
        transport = ReadOnlyTCPTransport("127.0.0.1", port)
        try:
            assert transport.receive(1) == b"x" * 4096
        finally:
            transport.close()


def test_silent_peer_timeout_is_effective() -> None:
    def script(connection: socket.socket) -> None:
        assert connection.recv(1) == b""

    with peer(script) as port:
        transport = ReadOnlyTCPTransport("127.0.0.1", port)
        start = monotonic()
        assert BoundedAcquisition(transport.receive, timeout_s=0.08).read().error_code == (
            "acquisition_timeout"
        )
        assert monotonic() - start < 1.0
        assert transport.stats().timeouts == 1
        assert not transport.stats().connected


def test_trickling_bytes_cannot_extend_total_deadline() -> None:
    def script(connection: socket.socket) -> None:
        for _ in range(30):
            try:
                connection.sendall(b"x")
            except OSError:
                break
            sleep(0.02)

    with peer(script) as port:
        transport = ReadOnlyTCPTransport("127.0.0.1", port)
        start = monotonic()
        with pytest.raises(TimeoutError):
            transport.receive(0.1)
        assert monotonic() - start < 0.5
        assert 0 < transport.stats().bytes_received < 30


def test_reconnect_preserves_identity_sequence_and_discards_partial_bytes() -> None:
    with peer(
        sends(frame() + b"\npartial"),
        sends(frame(1, "imposter") + b"\n" + frame(0) + b"\n" + frame(1) + b"\n"),
    ) as port:
        transport = ReadOnlyTCPTransport(
            "127.0.0.1", port, max_connection_attempts=2, reconnect_delay_s=0
        )
        source = MonitoredAcquisition(BoundedAcquisition(transport.receive))
        try:
            assert source.read().snapshot is not None
            assert source.read().error_code == "acquisition_transport_error"
            assert source.read().error_code == "acquisition_invalid_sequence"
            assert source.read().error_code == "acquisition_invalid_sequence"
            result = source.read()
            assert result.snapshot is not None and result.snapshot.step == 1
            assert source.read().error_code == "acquisition_transport_error"
            assert source.read().error_code == "acquisition_transport_error"
            assert transport.stats().connection_attempts == 2
            assert transport.stats().policy_rejections == 1
            assert source.stats().successful == 2
        finally:
            transport.close()


def test_cooldown_does_not_sleep_or_attempt_connection() -> None:
    with peer(sends(b"")) as port:
        transport = ReadOnlyTCPTransport("127.0.0.1", port, max_connection_attempts=2)
        with pytest.raises(OSError):
            transport.receive(1)
        start = monotonic()
        with pytest.raises(OSError, match="cooldown"):
            transport.receive(1)
        assert monotonic() - start < 0.5
        assert transport.stats().connection_attempts == 1
        transport.close()


def test_connect_and_receive_share_one_deadline() -> None:
    with (
        patch("ares.integrations.tcp_readonly.socket.socket") as factory,
        patch(
            "ares.integrations.tcp_readonly.monotonic",
            side_effect=[10, 10, 10.2, 10.6, 10.7, 10.8],
        ),
    ):
        factory.return_value.recv.return_value = b"ok\n"
        transport = ReadOnlyTCPTransport("127.0.0.1", 1234)
        assert transport.receive(1) == b"ok"
        timeouts = [call.args[0] for call in factory.return_value.settimeout.call_args_list]
        assert len(timeouts) == 2
        assert abs(timeouts[0] - 0.8) < 1e-9
        assert abs(timeouts[1] - 0.3) < 1e-9
        transport.close()


def test_connect_failure_closes_socket_and_consumes_budget() -> None:
    with patch("ares.integrations.tcp_readonly.socket.socket") as factory:
        factory.return_value.connect.side_effect = OSError("offline")
        transport = ReadOnlyTCPTransport("127.0.0.1", 1234)
        with pytest.raises(OSError, match="offline"):
            transport.receive(1)
        factory.return_value.close.assert_called_once()
        with pytest.raises(OSError, match="budget"):
            transport.receive(1)
        assert transport.stats().transport_errors == 1
        assert transport.stats().connection_attempts == 1


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), 3601])
def test_invalid_timeout_never_connects(timeout: float) -> None:
    transport = ReadOnlyTCPTransport("127.0.0.1", 1234)
    with pytest.raises(ValueError):
        transport.receive(timeout)
    assert transport.stats().connection_attempts == 0


@pytest.mark.parametrize("address", ["localhost", "invalid", "fe80::1%1"])
def test_dns_and_scoped_addresses_rejected(address: str) -> None:
    with pytest.raises(ValueError):
        ReadOnlyTCPTransport(address, 1234)


@pytest.mark.parametrize("port", [0, 65536, True])
def test_invalid_port(port: int) -> None:
    with pytest.raises(ValueError):
        ReadOnlyTCPTransport("127.0.0.1", port)


@pytest.mark.parametrize("attempts", [0, 101, True])
def test_invalid_budget(attempts: int) -> None:
    with pytest.raises(ValueError):
        ReadOnlyTCPTransport("127.0.0.1", 1234, max_connection_attempts=attempts)


@pytest.mark.parametrize("delay", [-1, float("inf"), float("nan")])
def test_invalid_delay(delay: float) -> None:
    with pytest.raises(ValueError):
        ReadOnlyTCPTransport("::1", 1234, reconnect_delay_s=delay)


def test_expired_deadline_rejected_before_socket_connect() -> None:
    with (
        patch("ares.integrations.tcp_readonly.socket.socket") as factory,
        patch("ares.integrations.tcp_readonly.monotonic", side_effect=[10, 10, 12, 12]),
    ):
        transport = ReadOnlyTCPTransport("::1", 1234)
        with pytest.raises(TimeoutError):
            transport.receive(1)
        factory.return_value.connect.assert_not_called()
        factory.return_value.close.assert_called_once()
