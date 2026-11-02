"""Local simulation demonstration of durable three-agent evidence audit."""

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from ares.runtime.evidence_team import evidence_team_reference_generate
from ares.runtime.evidence_team_ollama import ollama_evidence_team_generator
from ares.runtime.evidence_team_store import DurableEvidenceStore, run_durable_evidence_team
from ares.runtime.temporal_evidence import EvidenceReading


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARES durable evidence-team simulation")
    parser.add_argument("--db", type=Path, default=Path(".ares-evidence-team.sqlite"))
    parser.add_argument("--task-id", default="evidence-demo-01")
    parser.add_argument("--identity", default="offline-reference-v1")
    parser.add_argument("--temperatures", type=float, nargs="+", default=[65.0, 70.0, 75.0])
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--recover", action="store_true")
    args = parser.parse_args(argv)
    if args.live and args.identity == "offline-reference-v1":
        parser.error("live Ollama tasks require a unique --identity naming the model")
    readings = tuple(EvidenceReading(index, t) for index, t in enumerate(args.temperatures))
    generate = (
        ollama_evidence_team_generator(args.model)
        if args.live
        else evidence_team_reference_generate
    )
    store = DurableEvidenceStore(args.db)
    outcome = run_durable_evidence_team(
        store,
        generate,
        readings,
        task_id=args.task_id,
        identity=args.identity,
        recover=args.recover,
    )
    print(json.dumps({"task_id": args.task_id, "result": asdict(outcome)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
