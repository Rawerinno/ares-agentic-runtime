# Supervisor evaluation baseline

This baseline evaluates deterministic temperature classifications through
the same authorization-enforcing read gateway used in the application.

Scenarios: normal, warning boundaries, critical boundaries, overheating,
invalid non-finite telemetry, mismatched expectations and empty suites.

Run with `uv run pytest tests/evaluation -v`.

The result is classification accuracy on these fixed cases, **not** a
production reliability estimate, model intelligence score, or hardware
safety certification. Evaluations use only in-memory simulated sensors.
