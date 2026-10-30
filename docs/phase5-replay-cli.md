# Phase 5 — recorded replay CLI

Save a trusted local JSON list of sequential sensor observations with fields `device_id`, `step`, `temperature_c`, `healthy`. Each step starts at 0 and increments by 1. No network access or hardware interface is used.

Run:

```powershell
uv run python -m ares.integrations.replay_cli sample.json
```

The JSON report contains each authorized observation's severity and the supervisor's read-only recommendation. Bad or unavailable files return a rejected status and nonzero exit code. This is a simulated/recorded-data demonstration, not a real-device integration or a safety certification.
