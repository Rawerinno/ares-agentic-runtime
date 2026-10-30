"""Phase 5 recorded-only gates run without hardware or LLM."""

from typing import cast

from ares.evaluation.phase5_acceptance import phase5_acceptance


def test_recorded_replay_offline_gates() -> None:
    report = phase5_acceptance()
    assert report["passed"] == report["total"] == 3
    checks = cast("dict[str, bool]", report["checks"])
    assert all(checks.values())
    assert report["live_hardware_validated"] is False
    assert report["actuation_enabled"] is False
