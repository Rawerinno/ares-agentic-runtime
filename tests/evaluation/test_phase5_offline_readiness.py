"""The Phase 5 readiness CLI must never claim live-device validation."""

import json
from typing import cast
from unittest.mock import patch

from pytest import CaptureFixture

from ares.evaluation.phase5_offline_readiness import offline_readiness, run


def test_offline_readiness_gates() -> None:
    with patch("ares.integrations.tcp_readonly.socket.socket") as factory:
        report = offline_readiness()
    factory.assert_not_called()
    assert report["passed"] == report["total"] == 6
    assert all(cast("dict[str, bool]", report["checks"]).values())
    assert report["ready_for_live_hardware"] is False
    assert report["hardware_validated"] is False
    assert report["transport_authenticated"] is False
    assert report["actuation_enabled"] is False
    json.dumps(report, allow_nan=False)


def test_readiness_cli_emits_json_and_exit_code(capsys: CaptureFixture[str]) -> None:
    assert run([]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "offline-readiness"
    assert report["passed"] == report["total"] == 6


def test_failed_gate_causes_nonzero_exit(capsys: CaptureFixture[str]) -> None:
    with patch(
        "ares.evaluation.phase5_offline_readiness.phase5_acceptance",
        return_value={
            "passed": 0,
            "total": 1,
            "live_hardware_validated": False,
            "actuation_enabled": False,
        },
    ):
        assert run([]) == 1
    report = json.loads(capture.readouterr().out)
    assert report["checks"]["recorded_replay"] is False
