"""Bounded offline or local Ollama acceptance of evidence-first investigation.

Safety outcomes are not inferred from the model; followups are advisory only.
"""

import argparse
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

from ares.runtime.evidence_advisor import (
    ollama_evidence_generator,
    parse_followup,
    reference_followup,
)
from ares.runtime.temporal_evidence import EvidenceReading, EvidenceReport, analyze_evidence


@dataclass(frozen=True, slots=True)
class EvidenceCase:
    name: str
    readings: tuple[EvidenceReading, ...]
    expected: str


CASES = (
    EvidenceCase("single_normal", (EvidenceReading(0, 20.0),), "insufficient_history"),
    EvidenceCase("single_hot", (EvidenceReading(0, 85.0),), "insufficient_history"),
    EvidenceCase(
        "two_hot", (EvidenceReading(0, 75.0), EvidenceReading(1, 85.0)),
        "insufficient_history",
    ),
    EvidenceCase(
        "rising",
        (EvidenceReading(0, 60.0), EvidenceReading(1, 64.0), EvidenceReading(2, 68.0)),
        "rising_temperature",
    ),
    EvidenceCase(
        "stable",
        (EvidenceReading(0, 60.0), EvidenceReading(1, 60.0), EvidenceReading(2, 60.0)),
        "no_confirmed_rise",
    ),
    EvidenceCase(
        "cooling",
        (EvidenceReading(0, 85.0), EvidenceReading(1, 80.0), EvidenceReading(2, 75.0)),
        "no_confirmed_rise",
    ),
    EvidenceCase(
        "spike",
        (EvidenceReading(0, 50.0), EvidenceReading(1, 85.0), EvidenceReading(2, 51.0)),
        "no_confirmed_rise",
    ),
    EvidenceCase(
        "unhealthy",
        (EvidenceReading(0, 60.0), EvidenceReading(1, 65.0, healthy=False)),
        "invalid_telemetry",
    ),
    EvidenceCase(
        "nonfinite",
        (EvidenceReading(0, 20.0), EvidenceReading(1, float("nan"))),
        "invalid_telemetry",
    ),
)


def evaluate_evidence(
    generator: Callable[[EvidenceReport], str], *, repeats: int = 1
) -> dict[str, object]:
    if not 1 <= repeats <= 5:
        raise ValueError("repeats must be between 1 and 5")
    details: list[dict[str, object]] = []
    evidence_correct = 0
    model_accepted = 0
    model_errors = 0
    started = monotonic()
    for case in CASES:
        for iteration in range(repeats):
            evidence = analyze_evidence(case.readings)
            correct = (
                evidence.state.value == case.expected and evidence.device_actions == "disabled"
            )
            evidence_correct += int(correct)
            try:
                answer = generator(evidence)
                accepted, diagnostic = parse_followup(answer, evidence)
            except Exception:
                accepted, diagnostic = False, "model_exception"
                model_errors += 1
            model_accepted += int(accepted)
            details.append(
                {
                    "scenario": case.name,
                    "repeat": iteration + 1,
                    "evidence_state": evidence.state.value,
                    "evidence_correct": correct,
                    "model_accepted": accepted,
                    "diagnostic": diagnostic,
                    "safe_followup": evidence.suggested_followup,
                }
            )
    total = len(details)
    return {
        "scope": "evidence_first_investigator",
        "total_runs": total,
        "evidence_correct": evidence_correct,
        "model_accepted": model_accepted,
        "model_errors": model_errors,
        "acceptance_rate": round(model_accepted / total, 4),
        "device_actions": "disabled",
        "results": details,
        "wall_time_ms": round((monotonic() - started) * 1000, 2),
        "limitations": (
            "Synthetic evidence states, not verified physical diagnoses. "
            "Follow-up proposals are read-only advisory; no hardware use."
        ),
    }


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARES temporal evidence investigator acceptance")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output", type=Path, default=Path("ares-evidence-acceptance.json"))
    args = parser.parse_args(argv)
    generator = ollama_evidence_generator(args.model) if args.live else reference_followup
    report = evaluate_evidence(generator, repeats=args.repeats)
    report["model_source"] = "live_ollama" if args.live else "offline_reference"
    output = json.dumps(report, indent=2, sort_keys=True)
    args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if report["evidence_correct"] == report["total_runs"] else 1


if __name__ == "__main__":
    raise SystemExit(run())
