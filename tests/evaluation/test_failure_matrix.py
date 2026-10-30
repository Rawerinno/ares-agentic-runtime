"""Failure injection never gives invalid proposals operational authority."""

from typing import cast

from ares.evaluation.failure_matrix import failure_matrix


def test_invalid_model_outputs_are_fail_closed() -> None:
    report = failure_matrix()
    assert report["passed"] == report["total"] == 7
    rows = cast("list[dict[str, object]]", report["cases"])
    assert all(row["passed"] is True for row in rows)
    assert all(row["has_decision"] is False for row in rows[:-1])
    assert rows[-1]["governed_kind"] == "request_review"
    assert rows[-2]["error_code"] == "model_exception"
