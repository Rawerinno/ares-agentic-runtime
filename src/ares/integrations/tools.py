"""Explicit read-only capability boundary for the in-memory simulator.

This is an MCP-ready internal interface, not a networked MCP server.
Only a trusted registered simulator can be called through this gateway.
"""

from dataclasses import dataclass

from ares.safety import AuthorizationDecision, AuthorizationError, Capability, Policy
from ares.safety import RiskLevel, ToolRequest
from ares.simulation import DeviceSimulator, DeviceSnapshot


class ToolNotFoundError(LookupError):
    """Requested tool is not registered with this gateway."""


@dataclass(frozen=True, slots=True)
class SensorReadResult:
    """Structured result of one permitted simulated sensor observation."""

    tool_id: str
    snapshot: DeviceSnapshot


class ReadOnlyToolGateway:
    """Enforce authorization before dispatching an explicitly registered read.

    No arbitrary callbacks, dynamic tool calls, remote transports, or writes.
    High-risk reads are rejected until a trusted approval verifier exists.
    """

    def __init__(self, policy: Policy) -> None:
        self._policy = policy
        self._sensors: dict[str, DeviceSimulator] = {}

    def register_sensor(self, tool_id: str, sensor: DeviceSimulator) -> None:
        if not tool_id.strip():
            raise ValueError("tool_id must not be blank")
        if tool_id in self._sensors:
            raise ValueError("tool_id is already registered")
        self._sensors[tool_id] = sensor

    def read_sensor(
        self,
        *,
        agent_id: str,
        tool_id: str,
        risk: RiskLevel = RiskLevel.LOW,
    ) -> SensorReadResult:
        request = ToolRequest(agent_id, tool_id, Capability.READ, risk)
        decision = self._policy.decide(request)
        if decision is not AuthorizationDecision.ALLOW:
            raise AuthorizationError("Simulated read not automatically authorized")
        sensor = self._sensors.get(tool_id)
        if sensor is None:
            raise ToolNotFoundError(f"Unregistered tool: {tool_id}")
        return SensorReadResult(tool_id, sensor.read())
