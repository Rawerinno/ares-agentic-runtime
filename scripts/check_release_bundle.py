"""One-command, read-only validation of both CI release evidence bundles.

Usage:
    uv run python scripts/check_release_bundle.py --sha <MAIN_SHA> \
        --ubuntu <EXTRACTED_UBUNTU_DIR> --windows <EXTRACTED_WINDOWS_DIR>

Integrity and semantic checks are necessary, not sufficient, for a release.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import cast

from ares.evaluation.verify_release_report import validate_report
from verify_acceptance_artifacts import (
    REPORT,
    reject_duplicate_keys,
    reject_nonfinite_constant,
    verify,
)


def check(directory: Path, sha: str, runner: str) -> str:
    """Verify binding to the main commit and offline invariants of a single OS."""
    digest = verify(directory, sha, runner)
    report: object = json.loads(
        (directory / REPORT).read_text(encoding="utf-8"),
        object_pairs_hook=reject_duplicate_keys,
        parse_constant=reject_nonfinite_constant,
    )
    errors = validate_report(report)
    if errors:
        raise ValueError(f"{runner}: offline invariants rejected: {', '.join(errors)}")
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--ubuntu", required=True, type=Path)
    parser.add_argument("--windows", required=True, type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
        parser.error("--sha must be a full lowercase 40-character hexadecimal SHA")
    try:
        for runner, directory in (("ubuntu", args.ubuntu), ("windows", args.windows)):
            digest = check(directory, cast("str", args.sha), runner)
            print(f"{runner}: provenance and offline invariants verified; SHA-256 {digest}")
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"FAIL: {type(exc).__name__}", file=sys.stderr)
        return 1
    print("PASS: both evidence bundles validated; human release approval still required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
