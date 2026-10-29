"""CLI smoke tests require neither Ollama nor internet access."""

import json

from _pytest.capture import CaptureFixture

from ares.intelligence.ollama_demo import run


def test_cli_critical(capsys: CaptureFixture[str]) -> None:
    assert run(["--temperature", "85"]) == 0
    output: dict[str, object] = json.loads(capsys.readouterr().out)
    assert output["severity"] == "critical"
    assert output["proposal"] == "request_review"
    assert output["mode"] == "offline-reference"


def test_cli_normal(capsys: CaptureFixture[str]) -> None:
    assert run(["--temperature", "20"]) == 0
    output: dict[str, object] = json.loads(capsys.readouterr().out)
    assert output["severity"] == "normal"
    assert output["proposal"] == "observe"
