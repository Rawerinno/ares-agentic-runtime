"""Opt-in receive-only TCP telemetry; no application writes or background retries."""

import ipaddress
import socket
from dataclasses import dataclass
from math import isfinite
from time import monotonic


@dataclass(frozen=True, slots=True)
class TransportStats:
    connection_attempts: int
    connections: int
    frames: int
    bytes_received: int
    timeouts: int
    transport_errors: int
    framing_errors: int
    policy_rejections: int
    connected: bool
    closed: bool
    last_error: str | None


class ReadOnlyTCPTransport:
    """Single-owner, newline-framed receiver for an explicitly selected numeric IP.

    Construction performs no I/O. Each receive permits at most one connection
    attempt, within its total deadline. The attempt cap is lifetime-wide, even
    after successful connections; only constructing a new session resets it.
    TCP control packets still occur: read-only means zero application payloads.
    """

    def __init__(
        self,
        address: str,
        port: int,
        *,
        max_connection_attempts: int = 1,
        reconnect_delay_s: float = 1.0,
    ) -> None:
        ip = ipaddress.ip_address(address)
        if "%" in address:
            raise ValueError("scoped addresses are not supported")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("port must be an integer in 1..65535")
        if type(max_connection_attempts) is not int or not 1 <= max_connection_attempts <= 100:
            raise ValueError("max_connection_attempts must be an integer in 1..100")
        if not isfinite(reconnect_delay_s) or reconnect_delay_s < 0:
            raise ValueError("reconnect_delay_s must be finite and nonnegative")
        self._address = str(ip)
        self._port = port
        self._family = socket.AF_INET if ip.version == 4 else socket.AF_INET6
        self._max_attempts = max_connection_attempts
        self._delay = reconnect_delay_s
        self._socket: socket.socket | None = None
        self._buffer = bytearray()
        self._closed = False
        self._retry_at = 0.0
        self._attempts = 0
        self._connections = 0
        self._frames = 0
        self._bytes = 0
        self._timeouts = 0
        self._errors = 0
        self._framing_errors = 0
        self._rejections = 0
        self._last_error: str | None = None

    def stats(self) -> TransportStats:
        return TransportStats(
            self._attempts,
            self._connections,
            self._frames,
            self._bytes,
            self._timeouts,
            self._errors,
            self._framing_errors,
            self._rejections,
            self._socket is not None,
            self._closed,
            self._last_error,
        )

    @staticmethod
    def _remaining(deadline: float) -> float:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError("telemetry deadline exceeded")
        return remaining

    def _disconnect(self) -> None:
        connection, self._socket = self._socket, None
        self._buffer.clear()
        if connection is not None:
            connection.close()

    def close(self) -> None:
        """Permanently close this session; never reconnect after explicit close."""
        self._closed = True
        self._disconnect()

    def receive(self, timeout_s: float) -> bytes:
        """Return <=4096 bytes without LF, or raise TimeoutError/OSError.

        A timeout, EOF, oversize/empty frame, or socket failure discards all
        buffered bytes and closes the connection. Never replay a partial frame.
        Callers must serialize receive/close; no worker threads are created.
        """
        if not isfinite(timeout_s) or not 0 < timeout_s <= 3600:
            raise ValueError("timeout_s must be finite and in (0, 3600]")
        deadline = monotonic() + timeout_s
        if self._closed:
            return self._reject("closed")
        if self._socket is None:
            if self._attempts >= self._max_attempts:
                return self._reject("connection_budget_exhausted")
            if monotonic() < self._retry_at:
                return self._reject("reconnect_cooldown")
        try:
            if self._socket is None:
                self._attempts += 1
                self._socket = socket.socket(self._family, socket.SOCK_STREAM)
                self._socket.settimeout(self._remaining(deadline))
                self._socket.connect((self._address, self._port))
                self._connections += 1
            while True:
                self._remaining(deadline)
                newline = self._buffer.find(b"\n")
                if newline >= 0:
                    if newline == 0:
                        self._framing_errors += 1
                        raise OSError("empty telemetry frame")
                    frame = bytes(self._buffer[:newline])
                    del self._buffer[: newline + 1]
                    self._frames += 1
                    self._last_error = None
                    return frame
                if len(self._buffer) == 4097:
                    self._framing_errors += 1
                    raise OSError("telemetry frame exceeds 4096 bytes")
                self._socket.settimeout(self._remaining(deadline))
                chunk = self._socket.recv(4097 - len(self._buffer))
                if not chunk:
                    raise OSError("telemetry stream ended")
                self._bytes += len(chunk)
                self._buffer.extend(chunk)
        except TimeoutError:
            self._timeouts += 1
            self._last_error = "timeout"
            self._retry_at = monotonic() + self._delay
            self._disconnect()
            raise
        except OSError:
            self._errors += 1
            self._last_error = "transport_error"
            self._retry_at = monotonic() + self._delay
            self._disconnect()
            raise

    def _reject(self, reason: str) -> bytes:
        self._rejections += 1
        self._last_error = reason
        raise OSError(reason)
