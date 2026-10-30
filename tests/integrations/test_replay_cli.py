"""Recorded telemetry batch CLI uses authorized supervisor only."""

import json
from pathlib import Path
from typing import cast

from _pytest.capture import CaptureFixture

from ares.integrations.replay_cli import replay, run


def test_replay_classifies_all_recorded_steps(tmp_path: Path) -> None:
    path = tmp_path / "sample.json"
    path.write_text(
        json.dumps(
            [
                {"device_id": "fixture", "step": 0, "temperature_c": 22, "healthy": True},
                {"device_id": "fixture", "step": 1, "temperature_c": 67, "healthy": True},
                {"device_id": "fixture", "step": 2, "temperature_c": 85, "healthy": True},
                {"device_id": "fixture", "step": 3, "temperature_c": 25, "healthy": False},
            ]
        ),
        encoding="utf-8",
    )
    result = replay(path)
    assert result["total"] == 4
    cases = cast("list[dict[str, object]]", result["cases"])
    assert [case["severity"] for case in cases] == ["normal", "warning", "critical", "critical"]


def test_replay_rejects_bad_file(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{}", encoding="utf-8")
    assert run([str(path)]) == 1
    result: dict[str, object] = json.loads(capsys.readouterr().out)
    assert result["status"] == "rejected"
