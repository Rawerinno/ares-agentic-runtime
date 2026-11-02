"""Independent arithmetic-only LLM review: advisory, never a safety authority."""

from collections.abc import Sequence
from decimal import Decimal, InvalidOperation

from ares.evaluation.ollama_capability_boundary import Generate


def _finite_decimal(text: str) -> Decimal | None:
    if len(text) > 100:
        return None
    try:
        value = Decimal(text.strip())
    except InvalidOperation:
        return None
    return value if value.is_finite() and value.copy_abs() <= Decimal("1000000") else None


def independent_mean_review(
    measurements: Sequence[str], expected_mean: str, generate: Generate
) -> tuple[str, bool]:
    """Ask a separate model invocation to recompute mean from original numbers.

    Safety labels are excluded. Any error, mismatch, or invalid numeric result
    returns an untrusted rejection. The deterministic reviewer remains final.
    """
    if len(measurements) != 3:
        raise ValueError("exactly three measurements required")
    numbers: list[str] = []
    for measurement in measurements:
        if not measurement.endswith(" C"):
            raise ValueError("expected Celsius measurements")
        raw = measurement.removesuffix(" C")
        if _finite_decimal(raw) is None:
            raise ValueError("invalid measurement")
        numbers.append(raw)
    expected = _finite_decimal(expected_mean)
    if expected is None:
        raise ValueError("invalid expected mean")
    try:
        answer = generate(
            "Independently calculate the arithmetic mean of these three Celsius "
            f"measurements: {', '.join(numbers)}. Return only the number."
        )
    except Exception:
        return "", False
    result = _finite_decimal(answer)
    return answer, result is not None and result == expected
