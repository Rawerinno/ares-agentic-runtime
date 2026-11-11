# ARES v1.0 — release evidence manifest (candidate, not approval)

Snapshot prepared 2026-11-11 (UTC). This document is an **evidence index**, not a claim of production readiness. All demonstrations are simulation-only, read-only and advisory. No hardware, actuator or destructive action is authorised.

## Candidate identity

- Repository: `Rawerinno/ares-agentic-runtime`
- Baseline main SHA: `5f0d22e3bff21b8f55e95283ece0de8fdf801b02`
- Last integrated change: [PR #112](https://github.com/Rawerinno/ares-agentic-runtime/pull/112), retention of verified offline acceptance artifacts.
- Historical comparison (not rerun here): unsupervised 5/18, rejected PR #100 4/18, deterministic supervisor 18/18. PR #100 must **not** be reopened or used as a release baseline.

## Traceable CI evidence

[PR #112 CI run](https://github.com/Rawerinno/ares-agentic-runtime/actions/runs/43027735174) (head `230b9126ecc18b4b661e5588e8768452301f4c14`): both Ubuntu and Windows quality jobs reported success, including lint, format, type checking, tests/coverage, simulated offline release acceptance, invariant verification, build, and artifact upload.

Artifacts, as observed on 2026-11-11:

| OS | Artifact | Artifact ID | SHA-256 (GitHub artifact digest) | Expires (UTC) |
| --- | --- | --- | --- | --- |
| Ubuntu | `offline-acceptance-ubuntu-latest` | `13859370868` | `b0bc02302dcf674c6312a76c208e49e4c63a50a262391033b139f1560355e877` | 2026-11-25 13:17:29 |
| Windows | `offline-acceptance-windows-latest` | `13858941260` | `e3b282fbc4454097097569e1dd9284a75921bddfa11a29881f0630e5951b8b3d` | 2026-11-25 13:17:52 |

These digests identify the **uploaded artifact archives**, not necessarily the inner JSON files. Download and preserve the artifacts before expiry; verify the actual JSON reports with `python -m ares.evaluation.verify_release_report`. The successful PR run tested its **PR head**, not automatically the squash-merged main SHA above. A fresh post-merge main CI run or equivalent exact-SHA validation is required for final release approval.

## Release gates

1. **Offline**: at the exact candidate SHA, Ruff, format, Pyright, pytest, package build and `ares.evaluation.release_acceptance` plus `ares.evaluation.verify_release_report` must pass. Preserve the original JSON and the run URLs. Required report invariants: `scope=offline_stub_only`, `all_passed=true`, `device_actions=disabled`, `default_parallelism=1`, `scenario_count=121`.
2. **Security**: deterministic supervisor remains authoritative; audit chains reject ambiguous duplicate JSON keys; report limitations must not be altered; no actuator/device or destructive operation is enabled. Any failure blocks release.
3. **Live model**: follow [local validation checklist](v1-local-validation-checklist.md) with `llama3.2:3b` only after the offline gates pass. Capture full commit SHA, versions, commands, outputs and timestamps. The evidence-followup 18 runs (9 cases × 2) are a **different suite** from the historical 18-case supervisor benchmark. Do not compare their rates directly.
4. **Release decision**: any missing or failing required validation is `NOT RUN` or `BLOCKED`, never `PASSED`. Model proposals cannot grant permission for physical action. No claim of real-time or hardware safety follows from this release.

## Open risks and handoff

- **Local Ollama validation: NOT RUN** for this candidate; do not substitute historical results.
- **Post-merge exact-SHA validation: NOT CONFIRMED** by this manifest.
- **Repository visibility** was reported as public on 2026-11-11 despite the intended private configuration. Resolve access policy before distributing sensitive project material.
- **Hardware testing: NOT RUN / OUT OF SCOPE**. Keep device actions disabled.

Final operator evidence bundle: candidate SHA, post-merge CI URL and downloaded JSON artifacts, verified report, local command transcript and JSON outputs, model version, explicit limitations, and a signed-off decision. Until then the release state is **CANDIDATE — NOT APPROVED**.
