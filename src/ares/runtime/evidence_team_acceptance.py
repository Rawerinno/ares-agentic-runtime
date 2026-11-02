"""Offline and optional local-model acceptance for the experimental three-role team.

The critic is measured even when the first two model roles are rejected.
No actuator commands or approval capabilities are available in this runtime.
"""

import argparse
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from time import monotonic

from ares.runtime.evidence_acceptance import CASES
from ares.runtime.evidence_team import GovernedEvidenceTeam, evidence_team_reference_generate
from ares.runtime.evidence_team_ollama import ollama_evidence_team_generator


def evaluate_team(generate: Callable[[str], str], *, repeats: int = 1) -> dict[str, object]:
    if not 1 <= repeats <= 5:
        raise ValueError("repeats must be 1..5")
    attempted = {"investigator": 0, "planner": 0, "critic": 0}
    accepted = {"investigator": 0, "planner": 0, "critic": 0}
    rejections: dict[str, dict[str, int]] = {name: {} for name in attempted}
    detail: list[dict[str, object]] = []
    full_teams = 0
    critic_correctly_rejected = 0
    critic_missed_bad_proposal = 0
    start = monotonic()
    for case in CASES:
        for iteration in range(repeats):
            outcome = GovernedEvidenceTeam(generate).evaluate(case.readings)
            full_teams += int(outcome.team_accepted)
            peer_wrong = any(not role.accepted for role in outcome.roles[:2])
            critic = outcome.roles[-1]
            if peer_wrong and critic.accepted and critic.proposed == "inconsistent":
                critic_correctly_rejected += 1
            if peer_wrong and not critic.accepted:
                critic_missed_bad_proposal += 1
            for role in outcome.roles:
                attempted[role.role] += 1
                accepted[role.role] += int(role.accepted)
                if not role.accepted:
                    bucket = rejections[role.role]
                    bucket[role.diagnostic] = bucket.get(role.diagnostic, 0) + 1
            detail.append(
                {
                    "scenario": case.name,
                    "repeat": iteration + 1,
                    "severity": outcome.severity,
                    "evidence_state": outcome.evidence_state,
                    "risk_action": outcome.authorized_action,
                    "team_accepted": outcome.team_accepted,
                    "roles": [
                        {
                            "role": role.role,
                            "bounded_proposal": role.proposed,
                            "accepted": role.accepted,
                            "diagnostic": role.diagnostic,
                        }
                        for role in outcome.roles
                    ],
                }
            )
    total = len(detail)
    return {
        "scope": "experimental_evidence_governed_three_agents",
        "total_runs": total,
        "full_teams_accepted": full_teams,
        "team_acceptance_rate": round(full_teams / total, 4),
        "per_role_attempted": attempted,
        "per_role_accepted": accepted,
        "rejection_counts": rejections,
        "critic_correctly_detected_bad_peers": critic_correctly_rejected,
        "critic_missed_bad_peers": critic_missed_bad_proposal,
        "device_actions": "disabled",
        "safety_authority": "deterministic_evidence_risk",
        "results": detail,
        "wall_time_ms": round((monotonic() - start) * 1000, 2),
        "limitations": (
            "Experimental offline/simulated history, not a physical diagnosis. "
            "All roles are observational; the critique cannot authorize operations."
        ),
    }


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARES evidence-aware three-agent evaluation")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output", type=Path, default=Path("ares-evidence-team.json"))
    args = parser.parse_args(argv)
    generator = (
        ollama_evidence_team_generator(args.model)
        if args.live
        else evidence_team_reference_generate
    )
    report = evaluate_team(generator, repeats=args.repeats)
    report["model_source"] = "live_ollama" if args.live else "offline_reference"
    serialized = json.dumps(report, sort_keys=True, indent=2)
    args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if report["device_actions"] == "disabled" else 1


if __name__ == "__main__":
    raise SystemExit(run())
