"""Adversarial checks for the offline release report verifier."""

from copy import deepcopy
from typing import cast

from ares.evaluation.release_acceptance import acceptance_report
from ares.evaluation.verify_release_report import validate_report


def test_valid_reference_report() -> None:
    assert validate_report(acceptance_report()) == ()


def test_non_object_rejected() -> None:
    assert "report_not_object" in validate_report([])


def test_required_invariants_fail_closed() -> None:
    original = acceptance_report()
    mutations: tuple[tuple[str, object], ...] = (
        ("scope", "live_ollama"),
        ("scenario_count", 120),
        ("simulated_model_calls", 483),
        ("audit_entries_checked", 120),
        ("default_parallelism", 2),
        ("device_actions", "enabled"),
        ("all_passed", 1),
        ("passed", 0),
        ("total", 0),
        ("limitations", ""),
    )
    for key, replacement in mutations:
        altered = deepcopy(original)
        altered[key] = replacement
        assert validate_report(altered), key


def test_missing_and_failing_checks_rejected() -> None:
    original = acceptance_report()
    for change in ("missing", "failed", "non_boolean"):
        altered = deepcopy(original)
        checks = cast(dict[str, object], altered["checks"])
        if change == "missing":
            checks.pop("audit_chain")
        elif change == "failed":
            checks["audit_chain"] = False
        else:
            checks["audit_chain"] = 1
        assert validate_report(altered), change
