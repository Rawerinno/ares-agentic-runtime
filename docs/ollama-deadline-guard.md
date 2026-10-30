# Ollama request deadline checks

The local HTTP adapter now measures a monotonic budget starting before
the connection and checks it between response chunks and after the read.
A completed response past the budget is rejected.

**Important limitation:** Python's blocking urllib reads may exceed the
budget before execution returns to a check. This is therefore a
best-effort elapsed-time guard, **not an absolute or preemptive deadline**.
The existing per-socket timeout remains in place. No process isolation,
untrusted remote model provider or safety-critical real equipment is
supported. A hard deadline requires a separately cancellable worker
process or nonblocking transport and is not claimed here.
