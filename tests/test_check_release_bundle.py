"""The release bundle gate must check both provenance and acceptance semantics."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_release_bundle.py"
SHA = "a" * 40


def valid_report() -> dict[str, object]:
    check_names = (
        "default_sequential",
        "scenario_accuracy",
        "audit_chain",
        "extraction_fail_closed",
        "arithmetic_fail_closed",
        "independent_review_rejects_wrong",
        "independent_review_accepts_correct",
        "provider_failure_fail_closed",
        "extreme_input_rejected",
    )
    return {
        "scope": "offline_stub_only",
        "scenario_count": 121,
        "simulated_model_calls": 484,
        "audit_entries_checked": 121,
        "checks": dict.fromkeys(check_names, True),
        "passed": len(check_names),
        "total": len(check_names),
        "all_passed": True,
        "default_parallelism": 1,
        "device_actions": "disabled",
        "limitations": (
            "These tests validate deterministic software invariants, not "
            "Ollama generalization, live concurrency performance, or hardware safety."
        ),
    }


def write_bundle(folder: Path, os_name: str, report: dict[str, object]) -> None:
    folder.mkdir()
    data = folder / "ares-release-acceptance.json"
    data.write_text(json.dumps(report), encoding="utf-8")
    provenance = {
        "commit_sha": SHA,
        "event": "push",
        "runner_os": os_name,
        "report_file": data.name,
        "report_sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
    }
    (folder / "ares-acceptance-provenance.json").write_text(
        json.dumps(provenance), encoding="utf-8"
    )


def invoke(ubuntu: Path, windows: Path) -> subprocess.CompletedProcess[str]:
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


def test_both_exact_sha_bundles_pass(tmp_path: Path) -> None:
    ubuntu, windows = tmp_path / "ubuntu", tmp_path / "windows"
    write_bundle(ubuntu, "Linux", valid_report())
    write_bundle(windows, "Windows", valid_report())
    result = invoke(ubuntu, windows)
    assert result.returncode == 0, result.stderr
    assert "human release approval still required" in result.stdout


@pytest.mark.parametrize("field", ["device_actions", "all_passed", "scenario_count"])
def test_digest_valid_but_semantically_invalid_bundle_rejected(tmp_path: Path, field: str) -> None:
    ubuntu, windows = tmp_path / "ubuntu", tmp_path / "windows"
    write_bundle(ubuntu, "Linux", valid_report())
    altered = valid_report()
    altered[field] = {"device_actions": "enabled", "all_passed": False, "scenario_count": 0}[field]
    write_bundle(windows, "Windows", altered)
    result = invoke(ubuntu, windows)
    assert result.returncode == 1
    assert "FAIL:" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("initially_valid", [True, False])
def test_semantics_use_only_digest_verified_bytes(tmp_path: Path, initially_valid: bool) -> None:
    folder = tmp_path / "ubuntu"
    report = valid_report()
    report["all_passed"] = initially_valid
    write_bundle(folder, "Linux", report)
    # Execute in a separate interpreter to avoid changing the test process.
    # Replace the report immediately after the first read returns its bytes.
    code = """
import json
import sys
from pathlib import Path
from check_release_bundle import check

folder = Path(sys.argv[1])
sha = sys.argv[2]
target = folder / "ares-release-acceptance.json"
original = Path.read_bytes
calls = 0

def read_bytes(path):
    global calls
    data = original(path)
    if path == target:
        calls += 1
        changed = json.loads(data)
        changed["all_passed"] = not changed["all_passed"]
        target.write_text(json.dumps(changed), encoding="utf-8")
    return data

Path.read_bytes = read_bytes
try:
    check(folder, sha, "ubuntu")
except ValueError:
    outcome = "rejected"
else:
    outcome = "accepted"
assert calls == 1, calls
print(outcome)
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(folder), SHA],
        cwd=SCRIPT.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ("accepted" if initially_valid else "rejected")
