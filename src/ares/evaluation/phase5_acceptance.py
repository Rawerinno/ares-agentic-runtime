"""Offline Phase 5 entry gates for recorded telemetry integration."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from ares.integrations.recorded import RecordedSensor, RecordingError
from ares.integrations.replay_cli import replay


def phase5_acceptance() -> dict[str, object]:
    """Validate deterministic recorded replay without devices or a model."""
    with TemporaryDirectory(prefix="ares-phase5-") as folder:
        path = Path(folder) / "recording.json"
        samples = [
            {"device_id": "fixture", "step": 0, "temperature_c": 20, "healthy": True},
            {"device_id": "fixture", "step": 1, "temperature_c": 65, "healthy": True},
            {"device_id": "fixture", "step": 2, "temperature_c": 90, "healthy": True},
            {"device_id": "fixture", "step": 3, "temperature_c": 22, "healthy": False},
        ]
        path.write_text(json.dumps(samples), encoding="utf-8")
        result = replay(path)
        cases = cast("list[dict[str, object]]", result["cases"])
        classifications = [case["severity"] for case in cases]
        findings = cast("list[dict[str, object]]", result["findings"])
        codes = [finding["code"] for finding in findings]
        checks = {
            "replay_all_steps": result["total"] == 4,
            "jump_and_unhealthy_findings": codes.count("temperature_jump") == 3
            and codes.count("sensor_unhealthy") == 1,
            "no_unsupported_staleness_claim": result["staleness_assessed"] is False,
            "thresholds_and_unhealthy": classifications
            == ["normal", "warning", "critical", "critical"],
        }
        samples[1]["step"] = 0
        path.write_text(json.dumps(samples), encoding="utf-8")
        try:
            RecordedSensor.from_file(path)
            checks["reject_invalid_sequence"] = False
        except RecordingError:
            checks["reject_invalid_sequence"] = True
    return {
        "phase": 5,
        "scope": "recorded-read-only",
        "checks": checks,
        "passed": sum(checks.values()),
        "total": len(checks),
        "live_hardware_validated": False,
        "actuation_enabled": False,
    }
