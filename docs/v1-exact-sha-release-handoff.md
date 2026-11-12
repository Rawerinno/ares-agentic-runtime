# ARES v1.0 — exact-SHA release handoff (candidate only)

Updated 2026-11-12 UTC. This is a **release gate**, not an approval. Always use the *current* main HEAD; never treat a previously documented commit or a PR workflow as proof for a newer release candidate.

## Candidate identification

1. Read the latest `main` SHA from GitHub and record its full 40-character value as `CANDIDATE_SHA`. Confirm the checkout matches: `git fetch origin main && git checkout main && git pull --ff-only && git rev-parse HEAD`.
2. Freeze this SHA for the acceptance review. If main advances, restart the exact-SHA checks for the new candidate. Do not reuse evidence from an earlier SHA.
3. Historical reference: 5/18 unsupervised, 4/18 with rejected PR #100, and 18/18 supervised. These are **not** new test results. Never reopen PR #100.

## Exact-SHA CI gate

1. In [ARES Actions](https://github.com/Rawerinno/ares-agentic-runtime/actions/workflows/ci.yml), identify a **push** run on `main` whose `head_sha` equals `CANDIDATE_SHA` exactly. A green pull-request run is insufficient. If no such run is available, mark the gate **NOT CONFIRMED**.
2. Verify both Ubuntu and Windows jobs succeeded, including Ruff, formatting, Pyright, pytest, offline acceptance, report invariants, build, provenance verification, and artifact upload.
3. Download `offline-acceptance-ubuntu-latest` and `offline-acceptance-windows-latest` from that *same* run. Extract into separate directories (for example `evidence/ubuntu` and `evidence/windows`). Each must contain `ares-release-acceptance.json` and `ares-acceptance-provenance.json`.
4. In the exact-SHA checkout, run:

   ```powershell
   $sha = (git rev-parse HEAD).Trim()
   python scripts/verify_acceptance_artifacts.py --sha $sha --ubuntu evidence/ubuntu --windows evidence/windows
   python -m ares.evaluation.verify_release_report evidence/ubuntu/ares-release-acceptance.json
   python -m ares.evaluation.verify_release_report evidence/windows/ares-release-acceptance.json
   ```

   The first command checks downloaded evidence identity and SHA-256 integrity for both operating systems, **not** semantic acceptance; the latter two independently check report invariants. Any failure blocks release.
5. Preserve the exact commit SHA, workflow run URL and ID, job conclusions, artifact IDs, report SHA-256 digests, download date and verifier outputs. Archive SHA-256 is **not** the same as the inner JSON report SHA-256.

## Safety and release decision

Only simulated, read-only advisory behavior is in scope. Physical/device/destructive actions remain disabled. Deterministic supervision, human approvals, audit integrity and fail-closed behavior must not be weakened. CI does not prove real-world device safety.

Check repository visibility before release: the repository was observed **public** on 2026-11-12 despite the intended private policy. Do not upload secrets or sensitive evidence until access policy is corrected and confirmed.

Complete [local validation](v1-local-validation-checklist.md) with Ollama only when the operator is available. Record actual commands, model/version, results and failures; never infer live-model success from offline CI.

**Release status: CANDIDATE — NOT APPROVED** until exact-SHA main CI, both downloaded artifact verifications, access policy, and local validation are confirmed.
