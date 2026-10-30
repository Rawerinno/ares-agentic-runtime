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

A read returns `AcquisitionResult(snapshot=None, error_code=...)` for
invalid data, receive timeouts, and transport operating-system errors.
Rejected frames do not advance the sequence position. A subsequent valid
frame at the expected step is accepted, but hardware reconnect policy and
any missing-sample recovery require a separate, explicit design.

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
