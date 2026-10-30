# Phase 4 — Robustness acceptance gates

**Offline gates:** 18 deterministic-reference classification trials, 18 governed
classification trials, and seven mocked model-failure injection cases. The
function `phase4_acceptance()` reports individual gate outcomes; all gates must
pass before describing offline checks as complete.

**Live evidence already collected on Lenovo Slim:** 18 calls to local
`llama3.2:3b`, 6/18 raw category matches, 18/18 governed category matches,
0 errors/rejections, mean response 3351.16 ms, median 3362.86 ms. One
intentionally missing model returned `model_error` and
`deterministic_degraded` without changing critical classification.

**Remaining before Phase 4 closure:** probe malformed network replies,
slow/partial responses and timeouts; assess multiple-event storage corruption
and concurrency; repeat live trials where appropriate, and document absolute
timeout limitations. Structural consistency is not free-text fact checking.
No real hardware or industrial safety validation has been conducted.

This acceptance checklist is engineering guidance and not a certification.
