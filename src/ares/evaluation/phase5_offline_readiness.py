"""Single-command, deterministic Phase 5 offline readiness evidence.

No network connection, hardware discovery, device I/O or model call occurs.
This is a software acceptance summary, not permission for live operation.
"""

import json
from collections.abc import Sequence
from dataclasses import asdict

from ares.evaluation.phase5_acceptance import phase5_acceptance
from ares.evaluation.phase5_acquisition_acceptance import acquisition_acceptance
from ares.integrations.acquisition_diagnostics import acquisition_diagnostics
from ares.integrations.acquisition_metrics import AcquisitionStats
from ares.integrations.tcp_readonly import ReadOnlyTCPTransport


def offline_readiness() -> dict[str, object]:
    """Collect existing acceptance results and assert evidence-bound diagnostics."""
    replay = phase5_acceptance()
    acquisition = acquisition_acceptance()
    unused = AcquisitionStats(0, 0, 0, 0, 0, {})
    transport = ReadOnlyTCPTransport("127.0.0.1", 9)
    diagnostics = acquisition_diagnostics(unused, transport.stats())
    transport.close()
    evidence = diagnostics["evidence_limits"]
    checks = {
        "recorded_replay": replay["passed"] == replay["total"],
        "acquisition": acquisition["passed"] == acquisition["total"],
        "diagnostic_not_started": (
            diagnostics["acquisition"]["state"] == "not_started"
            and diagnostics["acquisition"]["acceptance_ratio"] is None
        ),
        "diagnostic_no_unproved_claims": (
            isinstance(evidence, dict)
            and all(value == "not_assessed" for value in evidence.values())
        ),
        "no_transport_connections": transport.stats().connection_attempts == 0,
        "no_hardware_or_actuation_claims": (
            replay["live_hardware_validated"] is False
            and acquisition["hardware_validated"] is False
            and replay["actuation_enabled"] is False
            and acquisition["actuation_enabled"] is False
        ),
    }
    return {
        "phase": 5,
        "mode": "offline-readiness",
        "passed": sum(checks.values()),
        "total": len(checks),
        "checks": checks,
        "recorded_replay": replay,
        "acquisition": acquisition,
        "hardware_validated": False,
        "actuation_enabled": False,
        "transport_authenticated": False,
        "ready_for_live_hardware": False,
    }


def run(argv: Sequence[str] | None = None) -> int:
    """Report readiness and return nonzero when an offline gate regresses."""
    if argv:
        raise ValueError("offline readiness accepts no arguments")
    report = offline_readiness()
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(run())
