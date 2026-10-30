# Phase 5 — opt-in TCP telemetry receiver

`ReadOnlyTCPTransport` is a concrete receive-only transport for a device or
gateway that **pushes** newline-delimited telemetry. Nothing connects on import
or construction. It is not registered as an agent tool and is not enabled by
default. There is no serial driver, discovery, request command, device reset,
actuator interface, or application-level write method.

## Wire contract and use

Each frame follows [the acquisition schema](phase5_acquisition.md), followed by
one LF byte. The LF does not count toward the 4096-byte payload limit. CRLF works
only if the CR fits inside that limit (JSON accepts trailing whitespace).
Empty frames, EOF, and oversized frames fail closed. Fragmented frames and
multiple frames in one packet are supported with at most 4097 buffered bytes.

Illustrative integration, **not an instruction to connect to hardware**:

```python
from ares.integrations.acquisition import BoundedAcquisition
from ares.integrations.acquisition_metrics import MonitoredAcquisition
from ares.integrations.tcp_readonly import ReadOnlyTCPTransport

# Replace only after endpoint review and hardware-entry approval.
transport = ReadOnlyTCPTransport("192.0.2.1", 9000)
source = MonitoredAcquisition(BoundedAcquisition(transport.receive, timeout_s=1.0))
try:
    result = source.read()
    acquisition_health = source.stats()
    transport_health = transport.stats()
finally:
    transport.close()
```

Only numeric IPv4/IPv6 addresses are accepted; DNS and scoped IPv6 are rejected.
No hostname resolver can therefore block outside the socket deadline. The caller
must serialize `receive`, `stats`, and `close`, and always close in `finally`.

## Deadline and reconnection policy

- `receive(timeout_s)` accepts a finite value in `(0, 3600]` seconds. One monotonic
  deadline covers connection and every partial read, including slow trickles.
  Socket timeouts use the remaining budget, never a fresh per-chunk budget.
- Expired deadlines fail before returning buffered frames. OS scheduling may
  delay exception delivery; this is bounded socket I/O, not a hard real-time
  guarantee. No orphan workers or background retry loops are used.
- A timeout, EOF, framing error, or socket error closes the connection and clears
  the buffer. Partial bytes are never combined with a later connection.
- Default: **one connection attempt for the entire object lifetime**, no retries.
  Opt-in `max_connection_attempts` accepts 1..100. Successful connections still
  consume this budget. Each caller-initiated read can attempt at most one connect.
- Following failure, `reconnect_delay_s` (default 1 second) is a minimum cooldown.
  Calls during cooldown fail immediately; they do not sleep or open sockets.
- Budget exhaustion stays closed. Explicit `close()` is permanent and idempotent.
  A new transport object is a deliberate new connection budget.
- Keep the **same `BoundedAcquisition` object** across reconnects. Device identity
  and expected step are never reset. Device changes, restarts at step zero, and
  gaps are rejected. No protocol request can ask the sender to retransmit, so a
  missed sample may require a separately reviewed new acquisition session.
- JSON/schema rejection consumes a delimited frame but does not close the TCP
  connection or advance the acquisition sequence. Framing failures close it.

## Observability

`TransportStats` is an immutable snapshot: connection attempts/successes, framed
messages, received bytes, timeouts, socket errors, framing errors, policy
rejections, connection/closed state, and a bounded last-error category. Framing
errors are a subset of transport errors. Frames count wire frames, including
ones later rejected by JSON/schema validation. Counters contain no payload,
endpoint, credentials, or unbounded error history. `MonitoredAcquisition` adds
accepted samples, rejection categories, and failure streaks. Neither metric
layer infers sensor health from connection success.

## Offline acceptance criteria

`uv run --frozen pytest tests/integrations/test_tcp_readonly.py --no-cov` checks:

1. Fragmentation and coalescing preserve complete frames and sequence; the peer
   receives zero application bytes from ARES.
2. Silent peers time out; continuous trickles cannot renew the total deadline.
   A deterministic socket test verifies that connect consumes the same budget.
3. Exactly 4096 payload bytes are accepted; oversized/empty frames and partial
   EOF close the connection without returning a sample.
4. Reconnection discards partial bytes, preserves identity/sequence validation,
   respects cooldown, and stops at the lifetime connection budget.
5. Explicit close prevents reopening; failed connects release the socket;
   invalid settings perform no connection attempt.
6. Acquisition and transport counters distinguish accepted samples, transport
   failures, policy blocks, and framing errors; snapshots remain independent.
7. A partial-frame timeout recovers on a new connection without replaying bytes;
   successful recovery clears the failure streak and last transport error.
8. A deterministic clock verifies reconnection exactly at cooldown expiry and
   rejects an already-buffered frame after its call deadline expires.
9. Repeated reads after budget exhaustion never create new sockets, and an
   injected connection reset discards partial data without application writes.

The repository CI runs these with the complete suite, strict types, lint,
formatting, coverage >=90%, and package build on Windows and Ubuntu.

## Remaining hardware and security gates

These tests use localhost peers and mocked socket faults only. They do not
validate real hardware, electrical safety, device firmware, or physical timing.
Read-only here means **no application payload is transmitted**; TCP handshakes,
acknowledgments, and connection teardown still reach the endpoint and may affect
its firmware. A reviewed endpoint must tolerate these operations.

This transport is plaintext TCP without peer authentication. A numeric address
and first-frame device ID are not proof of identity. Before any hardware use:

- Select an approved isolated endpoint, validate its push protocol and identity,
  and assess whether authenticated transport is required.
- Verify no actuators are connected/enabled and the firmware has no connection
  side effects. Review authorization before exposing acquisition to agents.
- Perform supervised device tests for silence, cable loss, reconnection,
  reboot/sequence discontinuity, and shutdown; record firmware and measurements.
- Decide explicitly how to start a new session after unrecoverable sample loss.

No physical tests or actuation were performed by this implementation.
