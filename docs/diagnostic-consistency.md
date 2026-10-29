# Diagnostic consistency checks

`check_consistency(assessment, report, hypotheses)` performs structural
cross-checks of a simulated sensor reading, the trusted supervisor severity,
the governed recommendation, and hypothesis statuses. The result includes
`passed` and a tuple of machine-readable `FindingCode` values.

It detects category/severity mismatches, invalid sensor telemetry, hypotheses
attached to normal readings, and disagreements from the untrusted model.
It does **not** verify the factual accuracy of free-text model suggestions,
prove root causes, certify industrial safety, or authorize actuation.

The local demo now emits `consistency_passed` and `consistency_findings`.
A model disagreement is surfaced as a finding even when deterministic
governance selected the appropriate recommendation.
