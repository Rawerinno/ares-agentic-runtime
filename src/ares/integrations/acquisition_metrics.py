"""Deterministic, read-only acquisition health accounting."""

from dataclasses import dataclass, field

from ares.integrations.acquisition import AcquisitionResult, BoundedAcquisition


@dataclass(frozen=True, slots=True)
class AcquisitionStats:
    attempts: int
    successful: int
    failed: int
    consecutive_failures: int
    max_consecutive_failures: int
    error_counts: dict[str, int]


@dataclass(slots=True)
class MonitoredAcquisition:
    """Collect bounded counters; never retry or send commands automatically."""

    source: BoundedAcquisition
    _attempts: int = 0
    _successful: int = 0
    _streak: int = 0
    _max_streak: int = 0
    _errors: dict[str, int] = field(default_factory=lambda: dict[str, int]())

    def read(self) -> AcquisitionResult:
        result = self.source.read()
        self._attempts += 1
        if result.error_code is None and result.snapshot is not None:
            self._successful += 1
            self._streak = 0
        else:
            code = result.error_code or "acquisition_inconsistent_result"
            self._errors[code] = self._errors.get(code, 0) + 1
            self._streak += 1
            self._max_streak = max(self._max_streak, self._streak)
        return result

    def stats(self) -> AcquisitionStats:
        """Return an independent snapshot; callers cannot mutate internal counts."""
        return AcquisitionStats(
            attempts=self._attempts,
            successful=self._successful,
            failed=self._attempts - self._successful,
            consecutive_failures=self._streak,
            max_consecutive_failures=self._max_streak,
            error_counts=dict(self._errors),
        )
