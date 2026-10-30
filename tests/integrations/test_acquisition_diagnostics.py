"""Diagnostics preserve evidence and do not perform I/O or authorize retries."""

import json
from dataclasses import replace
from typing import cast
from unittest.mock import patch

import pytest

from ares.integrations.acquisition import BoundedAcquisition
from ares.integrations.acquisition_diagnostics import acquisition_diagnostics
from ares.integrations.acquisition_metrics import AcquisitionStats, MonitoredAcquisition
from ares.integrations.tcp_readonly import ReadOnlyTCPTransport


def monitor(*items: bytes | BaseException) -> MonitoredAcquisition:
    pending = iter(items)

    def receive(_: float) -> bytes:
        item = next(pending)
        if isinstance(item, BaseException):
            raise item
        return item

    return MonitoredAcquisition(BoundedAcquisition(receive, expected_device_id="sensor-1"))


def frame(*, healthy: bool = True, device: str = "sensor-1") -> bytes:
    return json.dumps(dict(device_id=device, step=0, temperature_c=24, healthy=healthy)).encode()


def acquisition_part(report: dict[str, object]) -> dict[str, object]:
    return cast("dict[str, object]", report["acquisition"])


def test_not_started_has_no_ratio_or_transport_claim() -> None:
    source = monitor()
    report = acquisition_diagnostics(source.stats())
    assert acquisition_part(report)["state"] == "not_started"
    assert acquisition_part(report)["acceptance_ratio"] is None
    assert report["transport"] is None
    assert report["schema_version"] == 1
    assert json.loads(json.dumps(report, allow_nan=False)) == report


def test_failure_then_recovery_retains_historical_error_counts() -> None:
    source = monitor(TimeoutError(), frame(device="wrong"), frame())
    source.read()
    source.read()
    failed = acquisition_diagnostics(source.stats())
    assert acquisition_part(failed)["state"] == "last_read_failed"
    assert acquisition_part(failed)["acceptance_ratio"] == 0
    source.read()
    recovered = acquisition_diagnostics(source.stats())
    assert acquisition_part(recovered)["state"] == "last_read_accepted"
    assert acquisition_part(recovered)["acceptance_ratio"] == 1 / 3
    counters = cast("dict[str, object]", acquisition_part(recovered)["counters"])
    assert counters["failed"] == 2
    assert counters["consecutive_failures"] == 0
    assert counters["error_counts"] == {"acquisition_timeout": 1, "acquisition_device_mismatch": 1}
    assert acquisition_part(failed)["state"] == "last_read_failed"


def test_accepted_unhealthy_sample_does_not_imply_sensor_health() -> None:
    source = monitor(frame(healthy=False))
    result = source.read()
    assert result.snapshot is not None and not result.snapshot.healthy
    report = acquisition_diagnostics(source.stats())
    assert acquisition_part(report)["state"] == "last_read_accepted"
    assert report["evidence_limits"] == {
        "sensor_health": "not_assessed",
        "sample_freshness": "not_assessed",
        "peer_authentication": "not_assessed",
        "hardware_validation": "not_assessed",
    }


def test_report_does_not_alias_snapshot_or_future_reports() -> None:
    source = monitor(TimeoutError())
    source.read()
    snapshot = source.stats()
    report = acquisition_diagnostics(snapshot)
    counters = cast("dict[str, object]", acquisition_part(report)["counters"])
    errors = cast("dict[str, int]", counters["error_counts"])
    errors.clear()
    assert snapshot.error_counts == {"acquisition_timeout": 1}
    assert source.stats().error_counts == {"acquisition_timeout": 1}
    assert report != acquisition_diagnostics(snapshot)


@pytest.mark.parametrize(
    "last_error", ["reconnect_cooldown", "connection_budget_exhausted", "closed"]
)
def test_historical_policy_error_never_grants_retry_permission(last_error: str) -> None:
    transport = ReadOnlyTCPTransport("127.0.0.1", 1234)
    snapshot = replace(transport.stats(), last_error=last_error, policy_rejections=1)
    report = acquisition_diagnostics(monitor().stats(), snapshot)
    details = cast("dict[str, object]", report["transport"])
    assert details["last_error_observed"] == last_error
    assert details["retry_eligibility"] == "not_assessed"
    assert details["socket_state"] == "disconnected"


def test_open_socket_and_rejected_data_are_distinct_evidence() -> None:
    with patch("ares.integrations.tcp_readonly.socket.socket") as factory:
        factory.return_value.recv.return_value = frame(device="wrong") + b"\n"
        transport = ReadOnlyTCPTransport("127.0.0.1", 1234)
        source = MonitoredAcquisition(
            BoundedAcquisition(transport.receive, expected_device_id="sensor-1")
        )
        try:
            assert source.read().error_code == "acquisition_device_mismatch"
            report = acquisition_diagnostics(source.stats(), transport.stats())
            assert acquisition_part(report)["state"] == "last_read_failed"
            details = cast("dict[str, object]", report["transport"])
            assert details["socket_state"] == "socket_open"
            assert details["last_error_observed"] is None
            assert source.stats().failed == 1
            assert transport.stats().transport_errors == 0
        finally:
            transport.close()
        closed = acquisition_diagnostics(source.stats(), transport.stats())
        assert cast("dict[str, object]", closed["transport"])["socket_state"] == "closed"


def test_diagnostic_generation_performs_no_socket_or_acquisition_io() -> None:
    with patch("ares.integrations.tcp_readonly.socket.socket") as factory:
        transport = ReadOnlyTCPTransport("127.0.0.1", 1234)
        source = monitor()
        first = acquisition_diagnostics(source.stats(), transport.stats())
        second = acquisition_diagnostics(source.stats(), transport.stats())
        assert first == second
        factory.assert_not_called()
        assert source.stats().attempts == 0


def test_transport_timeout_is_not_added_to_acquisition_failures() -> None:
    acquisition = AcquisitionStats(1, 0, 1, 1, 1, {"acquisition_timeout": 1})
    transport = replace(ReadOnlyTCPTransport("127.0.0.1", 1234).stats(), timeouts=1)
    report = acquisition_diagnostics(acquisition, transport)
    counters = cast("dict[str, object]", acquisition_part(report)["counters"])
    assert counters["failed"] == 1
    assert acquisition_part(report)["acceptance_ratio"] == 0
