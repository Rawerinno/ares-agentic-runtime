"""Regression tests for fail-closed downloaded acceptance provenance verification."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_acceptance_artifacts.py"
SHA = "a" * 40


def write_artifact(directory: Path, runner_os: str) -> None:
    directory.mkdir()
    report = directory / "ares-release-acceptance.json"
    report.write_text('{"accepted": true}\n', encoding="utf-8")
    sidecar = {
        "commit_sha": SHA,
        "event": "push",
        "runner_os": runner_os,
        "report_file": report.name,
        "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
    }
    (directory / "ares-acceptance-provenance.json").write_text(
        json.dumps(sidecar), encoding="utf-8"
    )


def run_verifier(ubuntu: Path, windows: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--sha",
            SHA,
            "--ubuntu",
            str(ubuntu),
            "--windows",
            str(windows),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_accepts_matching_platform_artifacts(tmp_path: Path) -> None:
    ubuntu, windows = tmp_path / "ubuntu", tmp_path / "windows"
    write_artifact(ubuntu, "Linux")
    write_artifact(windows, "Windows")
    result = run_verifier(ubuntu, windows)
    assert result.returncode == 0, result.stderr
    assert "not a release approval" in result.stdout


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("missing_report", "missing report"),
        ("missing_sidecar", "missing report"),
        ("wrong_sha", "commit_sha mismatch"),
        ("wrong_event", "event mismatch"),
        ("wrong_os", "runner_os mismatch"),
        ("wrong_filename", "report_file mismatch"),
        ("wrong_digest", "report SHA-256 mismatch"),
        ("invalid_report", "report SHA-256 mismatch"),
        ("invalid_sidecar", "invalid provenance JSON"),
        ("extra_field", "unexpected provenance fields"),
        ("duplicate_field", "duplicate JSON key"),
    ],
)
def test_rejects_invalid_windows_artifact(tmp_path: Path, mutation: str, expected: str) -> None:
    ubuntu, windows = tmp_path / "ubuntu", tmp_path / "windows"
    write_artifact(ubuntu, "Linux")
    write_artifact(windows, "Windows")
    report = windows / "ares-release-acceptance.json"
    sidecar = windows / "ares-acceptance-provenance.json"
    if mutation == "missing_report":
        report.unlink()
    elif mutation == "missing_sidecar":
        sidecar.unlink()
    elif mutation == "invalid_report":
        report.write_text("{", encoding="utf-8")
    elif mutation == "invalid_sidecar":
        sidecar.write_text("{", encoding="utf-8")
    elif mutation == "duplicate_field":
        original = sidecar.read_text(encoding="utf-8")
        sidecar.write_text(
            original.replace('"event": "push"', '"event": "push", "event": "pull_request"'),
            encoding="utf-8",
        )
    else:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        if mutation == "wrong_sha":
            data["commit_sha"] = "b" * 40
        elif mutation == "wrong_event":
            data["event"] = "pull_request"
        elif mutation == "wrong_os":
            data["runner_os"] = "Linux"
        elif mutation == "wrong_filename":
            data["report_file"] = "other.json"
        elif mutation == "wrong_digest":
            data["report_sha256"] = "0" * 64
        elif mutation == "extra_field":
            data["untrusted"] = True
        sidecar.write_text(json.dumps(data), encoding="utf-8")
    result = run_verifier(ubuntu, windows)
    assert result.returncode != 0
    assert expected in result.stderr
