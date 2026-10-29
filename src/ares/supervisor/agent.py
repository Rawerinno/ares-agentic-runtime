"""Pure assessment of simulated engineering telemetry."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from ares.integrations import ReadOnlyToolGateway
from ares.simulation import DeviceSnapshot


class Severity(StrEnum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class Assessment:
    """Observation and recommendation, never an actuation command."""

    snapshot: DeviceSnapshot
    severity: Severity
    reason: str
    recommendation: str


class Supervisor:
    """Use an authorized gateway to assess a simulated temperature reading."""

    def __init__(
        self,
        gateway: ReadOnlyToolGateway,
        *,
        warning_c: float = 60.0,
        critical_c: float = 80.0,
    ) -> None:
        if not (isfinite(warning_c) and isfinite(critical_c)):
            raise ValueError("Thresholds must be finite")
        if warning_c >= critical_c:
            raise ValueError("Warning threshold must be below critical threshold")
        self._gateway = gateway
        self._warning_c = warning_c
        self._critical_c = critical_c

    def assess(self, *, agent_id: str, tool_id: str) -> Assessment:
        """Read only through the policy-enforcing tool boundary."""
        snapshot = self._gateway.read_sensor(
            agent_id=agent_id, tool_id=tool_id
        ).snapshot
        if not snapshot.healthy or not isfinite(snapshot.temperature_c):
            return Assessment(
                snapshot,
                Severity.CRITICAL,
                "Sensor reported an invalid or unhealthy reading",
                "Investigate the sensor; do not actuate automatically",
            )
        if snapshot.temperature_c >= self._critical_c:
            return Assessment(
                snapshot,
                Severity.CRITICAL,
                "Temperature at or above critical threshold",
                "Request engineer review before any corrective action",
            )
        if snapshot.temperature_c >= self._warning_c:
            return Assessment(
                snapshot,
                Severity.WARNING,
                "Temperature at or above warning threshold",
                "Increase monitoring and investigate thermal load",
            )
        return Assessment(
            snapshot,
            Severity.NORMAL,
            "Temperature within configured thresholds",
            "Continue observation",
        )
