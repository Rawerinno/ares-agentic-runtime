"""Authorization matrix tests with no real tool or hardware operations."""

from dataclasses import FrozenInstanceError

import pytest

from ares.safety import (
    Approval,
    AuthorizationDecision,
    AuthorizationError,
    Capability,
    Policy,
    RiskLevel,
    ToolRequest,
)


def req(
    capability: Capability = Capability.READ,
    risk: RiskLevel = RiskLevel.LOW,
    agent_id: str = "agent-1",
    tool_id: str = "sensor-1",
) -> ToolRequest:
    return ToolRequest(agent_id, tool_id, capability, risk)


def policy() -> Policy:
    return Policy(
        frozenset(
            {
                ("agent-1", "sensor-1", Capability.READ),
                ("agent-1", "sensor-1", Capability.WRITE),
            }
        )
    )


def approved() -> Approval:
    return Approval("agent-1", "sensor-1", Capability.WRITE, "engineer-1")


def test_denies_everything_by_default() -> None:
    p = Policy()
    assert p.decide(req()) is AuthorizationDecision.DENY
    with pytest.raises(AuthorizationError):
        p.authorize(req())


def test_granted_low_risk_read_is_allowed() -> None:
    assert policy().decide(req()) is AuthorizationDecision.ALLOW
    policy().authorize(req())


def test_write_requires_human_approval() -> None:
    request = req(Capability.WRITE)
    assert policy().decide(request) is AuthorizationDecision.REQUIRE_APPROVAL
    with pytest.raises(AuthorizationError):
        policy().authorize(request)
    policy().authorize(request, approved())


def test_high_risk_read_requires_approval() -> None:
    request = req(risk=RiskLevel.HIGH)
    assert policy().decide(request) is AuthorizationDecision.REQUIRE_APPROVAL
    with pytest.raises(AuthorizationError):
        policy().authorize(request)
    policy().authorize(request, Approval("agent-1", "sensor-1", Capability.READ, "engineer-1"))


@pytest.mark.parametrize(
    ("agent", "tool", "capability"),
    [
        ("agent-2", "sensor-1", Capability.WRITE),
        ("agent-1", "sensor-2", Capability.WRITE),
        ("agent-1", "sensor-1", Capability.READ),
    ],
)
def test_approval_cannot_cross_scope(agent: str, tool: str, capability: Capability) -> None:
    with pytest.raises(AuthorizationError):
        policy().authorize(
            req(Capability.WRITE),
            Approval(agent, tool, capability, "engineer-1"),
        )


def test_approval_never_overrides_missing_grant() -> None:
    with pytest.raises(AuthorizationError):
        Policy().authorize(req(Capability.WRITE), approved())


@pytest.mark.parametrize(
    ("agent", "tool"),
    [("", "sensor-1"), (" ", "sensor-1"), ("agent-1", "")],
)
def test_request_rejects_blank_identifiers(agent: str, tool: str) -> None:
    with pytest.raises(ValueError):
        ToolRequest(agent, tool, Capability.READ, RiskLevel.LOW)


def test_request_rejects_untyped_levels() -> None:
    with pytest.raises(ValueError):
        ToolRequest("a", "t", "read", RiskLevel.LOW)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ToolRequest("a", "t", Capability.READ, "low")  # type: ignore[arg-type]


def test_approval_rejects_invalid_fields() -> None:
    with pytest.raises(ValueError):
        Approval("", "t", Capability.WRITE, "engineer")
    with pytest.raises(ValueError):
        Approval("a", "", Capability.WRITE, "engineer")
    with pytest.raises(ValueError):
        Approval("a", "t", Capability.WRITE, " ")
    with pytest.raises(ValueError):
        Approval("a", "t", "write", "engineer")  # type: ignore[arg-type]


def test_contracts_are_immutable() -> None:
    request = req()
    with pytest.raises(FrozenInstanceError):
        request.tool_id = "other"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        approved().approved_by = "other"  # type: ignore[misc]
