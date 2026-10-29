"""Executable evaluation baseline for the deterministic supervisor."""

from ares.evaluation import EvalCase, evaluate_supervisor
from ares.supervisor import Severity


def test_full_reference_suite() -> None:
    cases = (
        EvalCase("ambient", 20.0, Severity.NORMAL),
        EvalCase("below_warning", 59.9, Severity.NORMAL),
        EvalCase("warning_boundary", 60.0, Severity.WARNING),
        EvalCase("below_critical", 79.9, Severity.WARNING),
        EvalCase("critical_boundary", 80.0, Severity.CRITICAL),
        EvalCase("overheat", 100.0, Severity.CRITICAL),
        EvalCase("invalid_nan", float("nan"), Severity.CRITICAL),
    )
    report = evaluate_supervisor(cases)
    assert report.total == 7
    assert report.passed == 7
    assert report.failures == ()
    assert report.accuracy == 1.0


def test_evaluation_identifies_mismatch() -> None:
    report = evaluate_supervisor((EvalCase("wrong", 20.0, Severity.CRITICAL),))
    assert report.total == 1
    assert report.passed == 0
    assert report.accuracy == 0.0
    assert len(report.failures) == 1


def test_empty_suite_is_explicitly_zero_accuracy() -> None:
    report = evaluate_supervisor(())
    assert report.total == 0
    assert report.passed == 0
    assert report.accuracy == 0.0
