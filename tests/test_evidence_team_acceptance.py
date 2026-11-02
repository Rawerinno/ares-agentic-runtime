"""Acceptance measures role quality and critic disagreement independently."""

import json
from pathlib import Path
from typing import cast

from pytest import CaptureFixture, MonkeyPatch

from ares.intelligence.transport import RequestLimits
from ares.runtime import evidence_team_ollama
from ares.runtime.evidence_team import evidence_team_reference_generate
from ares.runtime.evidence_team_acceptance import evaluate_team, run


def test_offline_reference_three_role_acceptance(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    report = evaluate_team(evidence_team_reference_generate)
    assert report["total_runs"] == 9
    assert report["full_teams_accepted"] == 9
    assert report["per_role_accepted"] == {"investigator": 9, "planner": 9, "critic": 9}
    assert report["critic_missed_bad_peers"] == 0
    assert report["device_actions"] == "disabled"
    output = tmp_path / "team.json"
    assert run(["--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8")) == json.loads(capsys.readouterr().out)


def test_bad_investigator_is_detected_instead_of_censoring_other_roles() -> None:
    def biased(prompt: str) -> str:
        if "ROLE=investigator." in prompt:
            return '{"followup":"inspect_thermal_system"}'
        return evidence_team_reference_generate(prompt)

    report = evaluate_team(biased)
    assert report["per_role_attempted"] == {"investigator": 9, "planner": 9, "critic": 9}
    assert report["per_role_accepted"] == {"investigator": 1, "planner": 9, "critic": 9}
    assert report["full_teams_accepted"] == 1
    assert report["critic_correctly_detected_bad_peers"] == 8
    assert report["critic_missed_bad_peers"] == 0


def test_bad_critic_is_counted_not_granted_approval() -> None:
    def rubber_stamp(prompt: str) -> str:
        if "ROLE=investigator." in prompt:
            return '{"followup":"inspect_thermal_system"}'
        if "ROLE=critic." in prompt:
            return '{"verdict":"consistent"}'
        return evidence_team_reference_generate(prompt)

    report = evaluate_team(rubber_stamp)
    assert report["full_teams_accepted"] == 1
    assert report["critic_missed_bad_peers"] == 8
    assert report["device_actions"] == "disabled"


def test_ollama_transport_receives_separate_no_tool_json_schemas(
    monkeypatch: MonkeyPatch,
) -> None:
    class MockTransport:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def request(self, payload: bytes, *, limits: RequestLimits) -> bytes:
            assert limits.max_response_bytes == 8192
            request = cast("dict[str, object]", json.loads(payload))
            self.calls.append(request)
            schema = cast("dict[str, object]", request["format"])
            fields = cast("list[str]", schema["required"])
            assert len(fields) == 1
            field = fields[0]
            answer = {
                "followup": "collect_more_samples",
                "action": "collect_evidence",
                "verdict": "consistent",
            }[field]
            return json.dumps({"response": json.dumps({field: answer})}).encode()

    fake = MockTransport()
    monkeypatch.setattr(evidence_team_ollama, "OllamaLocalTransport", lambda: fake)
    generator = evidence_team_ollama.ollama_evidence_team_generator("llama3.2:3b")
    for role in ("investigator", "planner", "critic"):
        assert isinstance(json.loads(generator(f"ROLE={role}. Context: {{}}")), dict)
    assert len(fake.calls) == 3
    assert all(req["stream"] is False and req["think"] is False for req in fake.calls)
    assert all("tools" not in req for req in fake.calls)


def test_runtime_errors_are_redacted_from_acceptance() -> None:
    secret = "PRIVATE_OAUTH_TOKEN"

    def broken(_prompt: str) -> str:
        raise RuntimeError(secret)

    report = evaluate_team(broken)
    assert report["full_teams_accepted"] == 0
    assert report["per_role_attempted"] == {"investigator": 9, "planner": 9, "critic": 9}
    assert secret not in json.dumps(report)
    assert report["device_actions"] == "disabled"
