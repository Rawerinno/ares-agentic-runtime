"""Run repeatable, isolated supervisor classification evaluations."""

from dataclasses import dataclass

from ares.integrations import ReadOnlyToolGateway
from ares.safety import Capability, Policy
from ares.simulation import DeviceSimulator
from ares.supervisor import Severity, Supervisor


@dataclass(frozen=True, slots=True)
class EvalCase:
    name: str
    temperature_c: float
    expected: Severity


@dataclass(frozen=True, slots=True)
class EvalReport:
    total: int
    passed: int
    failures: tuple[str, ...]

    @property
    def accuracy(self) -> float:
        return self.passed / self.total if self.total else 0.0


def evaluate_supervisor(cases: tuple[EvalCase, ...]) -> EvalReport:
    """Run isolated, policy-checked reads without modifying any device."""
    failures: list[str] = []
    for case in cases:
        gateway = ReadOnlyToolGateway(
            Policy(frozenset({("benchmark", "temperature", Capability.READ)}))
        )
        gateway.register_sensor(
            "temperature", DeviceSimulator("benchmark-sensor", initial_temperature_c=case.temperature_c)
        )
        actual = Supervisor(gateway).assess(agent_id="benchmark", tool_id="temperature").severity
        if actual is not case.expected:
            failures.append(f"{case.name}: expected {case.expected}, got {actual}")
    return EvalReport(total=len(cases), passed=len(cases) - len(failures), failures=tuple(failures))
