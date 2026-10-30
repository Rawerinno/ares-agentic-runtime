# Phase 5 — recorded telemetry reader

ARES accepts a bounded JSON array of recorded temperature samples via `RecordedSensor.from_file(Path(...))`. Each record must include exactly `device_id`, `step`, `temperature_c`, and `healthy`. Samples must use one nonblank device identifier and consecutive step numbers starting at zero. The adapter rejects missing or extra fields, non-finite temperatures, symlinks, oversized files, and invalid sequences.

The `read()` method never advances the replay; a trusted caller explicitly advances using `advance()`. This adapter can be registered with the existing policy-enforcing `ReadOnlyToolGateway` and consumed by `Supervisor`. The gateway does not grant actuation, and the model cannot directly access files or control devices.

This is **recorded-data integration only**: not a live PLC connector, industrial protocol implementation, or hardware safety verification. The file must be supplied by a trusted local operator; parent-directory races and filesystem attackers remain outside this prototype's security guarantees.
