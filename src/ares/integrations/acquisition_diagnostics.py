"""Pure diagnostic snapshots; never poll devices, retry, or infer sensor health."""

from dataclasses import asdict

from ares.integrations.acquisition_metrics import AcquisitionStats
from ares.integrations.tcp_readonly import TransportStats


def acquisition_diagnostics(
    acquisition: AcquisitionStats, transport: TransportStats | None = None
) -> dict[str, object]:
    """Describe supplied snapshots from one caller-owned acquisition session.

    Callers must capture both stats sequentially while reads are paused. Counters
    are cumulative; transport and acquisition failures overlap and are not added.
    The transport's last error is historical evidence, not retry permission.
    """
    if acquisition.attempts == 0:
        acquisition_state = "not_started"
    elif acquisition.consecutive_failures:
        acquisition_state = "last_read_failed"
    else:
        acquisition_state = "last_read_accepted"

    transport_report: dict[str, object] | None = None
    if transport is not None:
        if transport.closed:
            socket_state = "closed"
        elif transport.connected:
            socket_state = "socket_open"
        else:
            socket_state = "disconnected"
        transport_report = {
            "socket_state": socket_state,
            "counters": {
                "connection_attempts": transport.connection_attempts,
                "connections": transport.connections,
                "frames": transport.frames,
                "bytes_received": transport.bytes_received,
                "timeouts": transport.timeouts,
                "transport_errors": transport.transport_errors,
                "framing_errors": transport.framing_errors,
                "policy_rejections": transport.policy_rejections,
            },
            "last_error_observed": transport.last_error,
            "retry_eligibility": "not_assessed",
        }

    return {
        "schema_version": 1,
        "acquisition": {
            "state": acquisition_state,
            "counters": asdict(acquisition),
            "acceptance_ratio": (
                acquisition.successful / acquisition.attempts if acquisition.attempts else None
            ),
        },
        "transport": transport_report,
        "evidence_limits": {
            "sensor_health": "not_assessed",
            "sample_freshness": "not_assessed",
            "peer_authentication": "not_assessed",
            "hardware_validation": "not_assessed",
        },
    }
