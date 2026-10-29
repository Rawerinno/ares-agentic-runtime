"""Pure, fail-closed authorization policy. No tools are executed here."""

from dataclasses import dataclass
from enum import StrEnum


class Capability(StrEnum):
    READ = "read"
    WRITE = "write"


class RiskLevel(StrEnum):
    LOW = "low"
    HIGH = "high"


class AuthorizationDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class AuthorizationError(PermissionError):
    """Raised when an operation cannot be authorized."""


def _nonempty(value: str, field: str) -> None:
    if not value.strip():
        raise ValueError(f"{field} must not be blank")


@dataclass(frozen=True, slots=True)
class ToolRequest:
    """Caller, tool, and operation requiring authorization."""

    agent_id: str
    tool_id: str
    capability: Capability
    risk: RiskLevel

    def __post_init__(self) -> None:
        _nonempty(self.agent_id, "agent_id")
        _nonempty(self.tool_id, "tool_id")
        if type(self.capability) is not Capability:
            raise ValueError("capability must be Capability")
        if type(self.risk) is not RiskLevel:
            raise ValueError("risk must be RiskLevel")


@dataclass(frozen=True, slots=True)
class Approval:
    """Human approval bound to exactly one requester, tool and operation.

    Approvals carry no implied expiry or authenticity proof; trusted verification
    and durable approval storage must be implemented before real device actions.
    """

    agent_id: str
    tool_id: str
    capability: Capability
    approved_by: str

    def __post_init__(self) -> None:
        _nonempty(self.agent_id, "agent_id")
        _nonempty(self.tool_id, "tool_id")
        _nonempty(self.approved_by, "approved_by")
        if type(self.capability) is not Capability:
            raise ValueError("capability must be Capability")


@dataclass(frozen=True, slots=True)
class Policy:
    """Explicit allowlist of per-agent, per-tool capabilities.

    High-risk requests always require an approval decision; presence of approval
    is evaluated separately and only after the allowlist matches.
    """

    grants: frozenset[tuple[str, str, Capability]] = frozenset()

    def decide(self, request: ToolRequest) -> AuthorizationDecision:
        grant = (request.agent_id, request.tool_id, request.capability)
        if grant not in self.grants:
            return AuthorizationDecision.DENY
        if request.capability is Capability.WRITE or request.risk is RiskLevel.HIGH:
            return AuthorizationDecision.REQUIRE_APPROVAL
        return AuthorizationDecision.ALLOW

    def authorize(self, request: ToolRequest, approval: Approval | None = None) -> None:
        """Refuse everything except granted reads and matching approved actions.

        A caller-supplied Approval is not a trusted authorization token.
        This method is only appropriate for controlled tests until there is a
        server-side approval verification mechanism.
        """
        decision = self.decide(request)
        if decision is AuthorizationDecision.DENY:
            raise AuthorizationError("Tool capability is not granted")
        if decision is AuthorizationDecision.ALLOW:
            return
        if approval is None or (
            approval.agent_id != request.agent_id
            or approval.tool_id != request.tool_id
            or approval.capability is not request.capability
        ):
            raise AuthorizationError("Matching human approval is required")
