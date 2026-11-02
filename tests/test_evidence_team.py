"""Three-role evidence review checks faulty peers without granting execution authority."""

import json

import pytest

from ares.runtime.evidence_team import (
    GovernedEvidenceTeam,
    evidence_team_reference_generate,
)
from ares.runtime.temporal_evidence import EvidenceReading


def trace(*values: float) -> tuple[EvidenceReading, ...]:
    return tuple(EvidenceReading(index, value) for index, value in enumerate(values))


@pytest.mark.parametrize(
    ("readings", "severity", "action"),
    [
        (trace(20), "normal", "collect_evidence"),
        (trace(85), "critical", "human_review"),
        (trace(20, 24, 29), "normal", "inspect"),
        (trace(60, 60, 60), "warning", "inspect"),
        (trace(85, 80, 75), "critical", "human_review"),
        (trace(50, 85, 51), "critical", "human_review"),
        (trace(20, 20, 20), "normal", "monitor"),
        (trace(20, float("nan")), "critical", "validate_sensor"),
    ],
)
def test_reference_team_accepts_all_roles_without_actuation(
    readings: tuple[EvidenceReading, ...], severity: str, action: str
) -> None:
    calls: list[str] = []

    def generate(prompt: str) -> str:
        calls.append(prompt)
        return evidence_team_reference_generate(prompt)

    result = GovernedEvidenceTeam(generate).evaluate(readings)
    assert result.severity == severity
    assert result.authorized_action == action
    assert result.team_accepted
    assert len(calls) == 3
    assert [item.role for item in result.roles] == ["investigator", "planner", "critic"]
    assert all(item.accepted for item in result.roles)
    assert result.device_actions == "disabled"


def test_critic_can_identify_wrong_investigator_without_approving_it() -> None:
    def wrong_investigator(prompt: str) -> str:
        if "ROLE=investigator." in prompt:
            return '{"followup":"inspect_thermal_system"}'
        return evidence_team_reference_generate(prompt)

    result = GovernedEvidenceTeam(wrong_investigator).evaluate(trace(20))
    assert not result.team_accepted
    assert result.roles[0].diagnostic == "policy_mismatch"
    assert result.roles[1].accepted
    assert result.roles[2].proposed == "inconsistent"
    assert result.roles[2].accepted
    assert result.device_actions == "disabled"


def test_critic_can_identify_wrong_planner_without_approving_it() -> None:
    def wrong_planner(prompt: str) -> str:
        if "ROLE=planner." in prompt:
            return '{"action":"monitor"}'
        return evidence_team_reference_generate(prompt)

    result = GovernedEvidenceTeam(wrong_planner).evaluate(trace(85))
    assert not result.team_accepted
    assert result.roles[0].accepted
    assert not result.roles[1].accepted
    assert result.roles[2].accepted
    assert result.roles[2].proposed == "inconsistent"
    assert result.severity == "critical"
    assert result.authorized_action == "human_review"


def test_malformed_peer_is_redacted_but_critic_still_runs() -> None:
    secret = "private_payload_should_not_be_persisted"

    def malformed(prompt: str) -> str:
        if "ROLE=investigator." in prompt:
            return '{"followup":"validate_sensor","injected":"' + secret + '"}'
        return evidence_team_reference_generate(prompt)

    result = GovernedEvidenceTeam(malformed).evaluate(trace(20, 20, 20))
    assert not result.team_accepted
    assert result.roles[0].proposed == "unrecognized"
    assert result.roles[0].diagnostic == "invalid_fields"
    assert result.roles[2].accepted
    assert secret not in json.dumps(result, default=str)


def test_model_exception_is_isolated_and_safe() -> None:
    def unavailable(prompt: str) -> str:
        if "ROLE=planner." in prompt:
            raise RuntimeError("private token")
        return evidence_team_reference_generate(prompt)

    result = GovernedEvidenceTeam(unavailable).evaluate(trace(85))
    assert not result.team_accepted
    assert result.roles[1].diagnostic == "model_exception"
    assert result.roles[2].proposed == "inconsistent"
    assert result.roles[2].accepted
    assert result.authorized_action == "human_review"
    assert "private token" not in str(result)


def test_untrusted_critic_cannot_override_governor() -> None:
    def false_critic(prompt: str) -> str:
        if "ROLE=critic." in prompt:
            return '{"verdict":"inconsistent"}'
        return evidence_team_reference_generate(prompt)

    result = GovernedEvidenceTeam(false_critic).evaluate(trace(85, 80, 75))
    assert result.severity == "critical"
    assert result.authorized_action == "human_review"
    assert not result.team_accepted
    assert result.roles[-1].diagnostic == "policy_mismatch"
