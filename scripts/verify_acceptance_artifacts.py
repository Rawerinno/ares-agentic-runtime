"""Verify downloaded Ubuntu/Windows ARES acceptance evidence without devices.

Usage:
    python scripts/verify_acceptance_artifacts.py --sha <40-char-main-sha> \
        --ubuntu path/to/ubuntu --windows path/to/windows
The directories must contain the two *extracted* JSON files from each CI artifact.
This verifies provenance/integrity only, not the report's semantic invariants.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPORT = "ares-release-acceptance.json"
PROVENANCE = "ares-acceptance-provenance.json"
EXPECTED_OS = {"ubuntu": "Linux", "windows": "Windows"}
EXPECTED_FIELDS = {"commit_sha", "event", "runner_os", "report_sha256", "report_file"}


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject ambiguous JSON objects, including nested duplicate keys."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_nonfinite_constant(value: str) -> None:
    """Reject non-standard JSON NaN and Infinity values."""
    raise ValueError(f"non-finite JSON constant: {value}")


def verify(directory: Path, sha: str, os_name: str) -> str:
    report = directory / REPORT
    provenance = directory / PROVENANCE
    if not report.is_file() or not provenance.is_file():
        raise ValueError(f"{directory}: missing report or provenance JSON")
    try:
        data = json.loads(
            provenance.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"{directory}: invalid provenance JSON: {exc}") from exc
    if not isinstance(data, dict) or set(data) != EXPECTED_FIELDS:
        raise ValueError(f"{directory}: unexpected provenance fields")
    expected = {
        "commit_sha": sha,
        "event": "push",
        "runner_os": EXPECTED_OS[os_name],
        "report_file": REPORT,
    }
    for field, value in expected.items():
        if data[field] != value:
            raise ValueError(f"{directory}: {field} mismatch")
    digest = hashlib.sha256(report.read_bytes()).hexdigest()
    if (
        not isinstance(data["report_sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", data["report_sha256"])
        or data["report_sha256"] != digest
    ):
        raise ValueError(f"{directory}: report SHA-256 mismatch")
    try:
        report_data = json.loads(
            report.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonfinite_constant,
        )
        if not isinstance(report_data, dict):
            raise ValueError("top-level report must be a JSON object")
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"{directory}: invalid report JSON: {exc}") from exc
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True, help="Exact main commit SHA")
    parser.add_argument("--ubuntu", required=True, type=Path)
    parser.add_argument("--windows", required=True, type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
        parser.error("--sha must be a full lowercase 40-character hexadecimal SHA")
    try:
        for name, directory in (("ubuntu", args.ubuntu), ("windows", args.windows)):
            digest = verify(directory, args.sha, name)
            print(f"{name}: provenance verified; report SHA-256 {digest}")
    except (ValueError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print("PASS: both artifact provenances verified (not a release approval)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
