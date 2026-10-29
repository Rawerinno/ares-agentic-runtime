"""CLI smoke tests require neither Ollama nor internet access."""

import json
from typing import cast

from _pytest.capture import CaptureFixture

from ares.intelligence.ollama_demo import run


def test_cli_critical(capsys: CaptureFixture[str]) -> None:
    assert run(["--temperature", "85"]) == 0
    output: dict[str, object] = json.loads(capsys.readouterr().out)
    assert output["severity"] == "critical"
    assert output["proposal"] == "request_review"
    assert output["mode"] == "offline-reference"
    assert output["governed_proposal"] == "request_review"
    evidence = cast("list[dict[str, object]]", output["evidence"])
    assert evidence[0]["source"] == "sensor"


def test_cli_normal(capsys: CaptureFixture[str]) -> None:
    assert run(["--temperature", "20"]) == 0
    output: dict[str, object] = json.loads(capsys.readouterr().out)
    assert output["severity"] == "normal"
    assert output["proposal"] == "observe"
    assert output["governed_proposal"] == "observe"
    assert output["model_consistent"] is True
