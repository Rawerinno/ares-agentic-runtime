"""Offline Phase 4 acceptance gates; never assert hardware safety certification."""

from dataclasses import dataclass

from ares.evaluation.failure_matrix import failure_matrix
from ares.evaluation.ollama_benchmark import benchmark


@dataclass(frozen=True, slots=True)
class Gate:
    name: str
    passed: bool
    detail: str


def phase4_acceptance() -> dict[str, object]:
    """Run repeatable no-network checks; live LLM evidence is a separate gate."""
    baseline = benchmark(repeats=3)
    failures = failure_matrix()
    gates = (
        Gate(
            "offline_reference",
            baseline["passed"] == baseline["total"],
            "Deterministic reference passed all 18 fixed scenario evaluations",
        ),
        Gate(
            "governed_classification",
            baseline["governed_passed"] == baseline["total"],
            "Governed categories match the fixed reference cases",
        ),
        Gate(
            "model_fault_injection",
            failures["passed"] == failures["total"],
            "Seven invalid/valid mocked-model cases behave as expected",
        ),
    )
    return {
        "phase": 4,
        "scope": "offline-only",
        "passed": sum(gate.passed for gate in gates),
        "total": len(gates),
        "gates": [
            {"name": gate.name, "passed": gate.passed, "detail": gate.detail}
            for gate in gates
        ],
        "live_validation_required": True,
        "hardware_safety_certified": False,
    }
