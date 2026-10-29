# Diagnostic evidence and model boundary

ARES separates four concepts:

1. **Sensor evidence** is the observed temperature and health flag.
2. **Supervisor assessment** is a deterministic threshold-based severity and reason.
3. **Governed recommendation** derives only from that severity.
4. **Model explanation** is optional, unverified advisory text. It is excluded
   if the model's proposed action disagrees with the deterministic policy.

`build_diagnostic_report(assessment, proposal)` creates an immutable
`DiagnosticReport` with source-labelled evidence, trusted explanation,
model-consistency indicator and an explicit limitation. No device writes are
available through this API.

A single temperature reading cannot establish why equipment is hot, whether
the sensor is calibrated, or whether action is safe. Model output is not
evidence, a diagnosis or authorization. An untrusted narrative may still be
incorrect even when the action category is consistent. Future evaluation must
test factual support and contradiction, not merely category agreement.

The current supervisor is simulated and assumes configured thresholds of
60 C warning and 80 C critical. Those thresholds are examples, not
general-purpose safety limits.
