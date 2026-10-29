"""Verify an explicitly selected local ARES audit JSONL file."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from ares.evaluation.audit import AuditIntegrityError
from ares.evaluation.audit_storage import read_audit


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a local ARES audit chain")
    parser.add_argument("file", type=Path, help="Existing JSONL audit file")
    args = parser.parse_args(argv)
    if not args.file.is_file():
        print(json.dumps({"valid": False, "error_code": "audit_file_missing"}))
        return 1
    try:
        entries = read_audit(args.file)
    except (AuditIntegrityError, OSError, UnicodeError):
        print(json.dumps({"valid": False, "error_code": "audit_invalid"}))
        return 1
    print(
        json.dumps(
            {
                "valid": True,
                "count": len(entries),
                "last_digest": entries[-1].digest if entries else None,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
