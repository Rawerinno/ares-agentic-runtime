"""Read-only replay of recorded telemetry through policy and supervisor."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from ares.integrations import ReadOnlyToolGateway
from ares.integrations.recorded import RecordedSensor, RecordingError
from ares.integrations.replay_anomalies import analyze_recording
from ares.safety import Capability, Policy
from ares.simulation import DeviceSnapshot
from ares.supervisor import Supervisor


def replay(path: Path) -> dict[str, object]:
    """Classify every recorded event; never contact or actuate a device."""
    sensor = RecordedSensor.from_file(path)
    gateway = ReadOnlyToolGateway(
        Policy(frozenset({("supervisor", "recorded.temperature", Capability.READ)}))
    )
    gateway.register_sensor("recorded.temperature", sensor)
    supervisor = Supervisor(gateway)
    cases: list[dict[str, object]] = []
    snapshots: list[DeviceSnapshot] = []
    while True:
        outcome = supervisor.assess(agent_id="supervisor", tool_id="recorded.temperature")
        snapshots.append(outcome.snapshot)
        cases.append(
            {
                "step": outcome.snapshot.step,
                "temperature_c": outcome.snapshot.temperature_c,
                "healthy": outcome.snapshot.healthy,
                "severity": outcome.severity.value,
                "recommendation": outcome.recommendation,
            }
        )
        try:
            sensor.advance()
        except RecordingError as exc:
            if str(exc) != "recording_exhausted":
                raise
            break
    findings = analyze_recording(tuple(snapshots))
    return {
        "mode": "recorded-read-only",
        "total": len(cases),
        "cases": cases,
        "findings": [{"step": f.step, "code": f.code} for f in findings],
        "staleness_assessed": False,
    }


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARES recorded telemetry replay")
    parser.add_argument("recording", type=Path)
    args = parser.parse_args(argv)
    try:
        result = replay(args.recording)
    except (RecordingError, OSError) as exc:
        print(json.dumps({"status": "rejected", "error_code": type(exc).__name__}))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
