# ARES v1.0 — exact-SHA release handoff (candidate only)

Updated 2026-11-11 UTC. This is a **release gate**, not an approval or a substitute for actual CI evidence.

## Candidate

- Candidate `main` commit: `0e768351872a36cbb8bd520341eef43283a22839` (merged [PR #114](https://github.com/Rawerinno/ares-agentic-runtime/pull/114)).
- Earlier [release evidence manifest](v1-release-evidence-manifest.md) is a **historical snapshot** of PR #112; its baseline SHA and artifact digests do not validate this candidate.
- [Local validation checklist](v1-local-validation-checklist.md) remains the operator handoff.
- Historical 5/18 unsupervised, 4/18 on rejected PR #100, and 18/18 supervised are **not rerun** results. Do not reopen PR #100.

## Exact-SHA CI gate

1. Locate the **push-to-main** GitHub Actions run whose `head_sha` is **exactly** `0e768351872a36cbb8bd520341eef43283a22839`. A successful pull-request run is not a substitute.
2. Confirm both Ubuntu and Windows jobs completed successfully, including Ruff, formatting, Pyright, pytest, offline acceptance, invariant verification, package build, provenance validation and artifact upload.
3. Download **both** `offline-acceptance-ubuntu-latest` and `offline-acceptance-windows-latest` artifacts before their retention deadline. In each, require both `ares-release-acceptance.json` and `ares-acceptance-provenance.json`.
4. For each operating system, independently recompute the report's SHA-256 and compare to `report_sha256`; require `commit_sha` to match the candidate above, `event` to equal `push`, `runner_os` to match the job, and `report_file` to equal `ares-release-acceptance.json`. Run `python -m ares.evaluation.verify_release_report` on each downloaded report in the exact candidate checkout. Do not confuse the archive digest with the inner JSON digest.
5. Preserve run URL, run ID, artifact IDs, hashes, download date and verification output. **Any missing run, artifact, field or check is NOT CONFIRMED, not PASSED.**

## Security and release decision

Only simulation, read-only advisory behavior is in scope. Device/actuator/destructive actions stay disabled; deterministic supervision, human approvals and audit invariants must remain enforced. Do not infer physical or real-time safety from CI. The repository was reported **public** despite the intended private policy; confirm and correct visibility before sharing sensitive content. Local Ollama tests are **NOT RUN** for this candidate until executed and recorded by the operator. Release status: **CANDIDATE — NOT APPROVED** pending exact-SHA main CI, artifact verification, access policy and local validation.
