"""Deterministic stress checks of the bounded three-role safety boundary.

These tests do not measure Ollama's accuracy. They verify that Python always
rejects untrusted arithmetic and keeps risk classification authoritative.
"""

from decimal import Decimal
from random import Random

import pytest

from ares.evaluation.bounded_team import evaluate_team


@pytest.mark.parametrize(
    ("temperature", "severity"),
    [
        ("-20", "normal"),
        ("0", "normal"),
        ("59.999", "normal"),
        ("60", "warning"),
        ("60.001", "warning"),
        ("79.999", "warning"),
        ("80", "critical"),
        ("80.001", "critical"),
        ("200", "critical"),
    ],
)
def test_threshold_boundaries_are_deterministic(
    temperature: str, severity: str
) -> None:
    # Three identical readings make the expected average unambiguous.
    def model(question: str) -> str:
        if "Extract" in question:
            return temperature
        return temperature

    readings = (f"{temperature} C",) * 3
    result = evaluate_team(readings, model)
    assert result.status == "verified"
    assert result.severity == severity


def test_many_simple_deterministic_cases() -> None:
    random = Random(2026)
    for _ in range(100):
        temperature = random.randint(-100, 150)
        expected = (
            "critical" if temperature >= 80 else "warning" if temperature >= 60
            else "normal"
        )

        def model(_question: str) -> str:
            return str(temperature)

        result = evaluate_team((f"{temperature} C",) * 3, model)
        assert result.status == "verified"
        assert result.severity == expected


def test_wrong_average_never_produces_classification() -> None:
    def wrong(question: str) -> str:
        if "Extract" in question:
            return "80"
        return "0"

    result = evaluate_team(("80 C", "80 C", "80 C"), wrong)
    assert result.status == "rejected"
    assert result.severity is None
    assert result.errors == ("arithmetic_mismatch",)


def test_exact_decimal_equivalence_survives_formatting() -> None:
    def model(question: str) -> str:
        if "Extract" in question:
            return "6e1"
        return "60.0000"

    result = evaluate_team(("60.0 C", "60 C", "60.00 C"), model)
    assert result.status == "verified"
    assert result.severity == "warning"
    assert Decimal(result.verified_mean or "0") == Decimal("60")
