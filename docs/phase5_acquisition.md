# Phase 5 — read-only acquisition contract

The ARES acquisition boundary accepts a caller-provided `receive(timeout_s) -> bytes`
callable. It **does not** open serial ports or network connections, and has no
actuation surface.

## Frame format

Each frame is a UTF-8 JSON object containing exactly the following fields:

```json
{"device_id":"sensor-1","step":0,"temperature_c":22.5,"healthy":true}
```

- `device_id`: a non-empty string, stable across a session
- `step`: a zero-based, strictly consecutive integer
- `temperature_c`: a finite JSON number; booleans are rejected
- `healthy`: a JSON boolean
- Maximum frame size: **4096 bytes**
- Duplicate fields, extra fields, NaN and Infinity are rejected

## Failure semantics

Callers may set `expected_device_id="sensor-1"` on `BoundedAcquisition` before
any read. It must be a nonblank string; `None` retains the legacy first-accepted
sample identity binding. A configured value is compared exactly, without
trimming or case folding. Schema-valid messages from another device return
`acquisition_device_mismatch` before sequence validation. Rejections leave the
expected identity and next sequence unchanged and are included in monitoring.
This is a consistency check, not cryptographic device authentication.

A read returns `AcquisitionResult(snapshot=None, error_code=...)` for
invalid data, receive timeouts, and transport operating-system errors.
Rejected frames do not advance the sequence position. A subsequent valid
frame at the expected step is accepted, but hardware reconnect policy and
any missing-sample recovery require a separate, explicit design.

Numeric overflow during conversion is an invalid-schema error, and JSON that
exceeds the parser's nesting limit is an invalid-JSON error. Both remain inside
the structured failure boundary, leave sequence state unchanged, and are counted
by acquisition metrics. Recorded-file loading similarly reports `RecordingError`
for numeric overflow and excessive nesting.

The `timeout_s` parameter is passed to the injected receiver. **ARES does
not enforce elapsed wall-clock time around a blocking receiver**. A real
serial/network adapter must independently implement that deadline, bound its
read size, and avoid unbounded buffering. Do not use an unbounded blocking
function as the receiver.

## Safety and evidence

The boundary is read-only and is not a hardware driver. It has no commands
for controlling actuators, device reset, or port configuration. Transport
errors must not be interpreted as a healthy sensor reading. The existing
recorded replay system and its severity classification are separate from
live-device safety guarantees.

## Hardware entry criteria

1. Choose and document a concrete serial/network receive implementation
   with proven read timeout, bounded frames, and a disconnection policy.
2. Define a deliberate session/reconnection reset policy that does not
   silently accept device identity changes.
3. Inject transport and malformed-frame failures in automated tests.
4. Validate an actual device in read-only mode, with no actuators connected.
5. Review audit and authorization boundaries before exposing new devices.

No live-hardware validation is claimed by these offline tests.

## Concrete receive-only transport

An opt-in [TCP receiver](phase5_tcp_readonly.md) now implements the deadline,
bounded newline framing, connection budget, cooldown, and transport counters.
The boundary above remains transport-neutral. No hardware endpoint is enabled
or registered as an agent tool. The TCP implementation is validated only with
offline loopback peers and injected faults; hardware entry gates still apply.
