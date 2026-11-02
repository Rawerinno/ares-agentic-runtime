# Risk and evidence are independent

The first live temporal-evidence benchmark accepted 4/9 model follow-ups.
The model selected `inspect_thermal_system` in all five failures:
stable 60°C, cooling 85→75°C, isolated 85°C spike, and two invalid
telemetry histories. The legacy temporal-evidence follow-up benchmark
marks those as wrong because it measures *trend follow-up only*.
It should not be interpreted as an authoritative safety recommendation.

The `evidence_risk.reconcile` component is deliberately independent
of the model and combines:

- **Evidence state**, based only on the bounded time series:
  insufficient observations, sustained rise, unconfirmed rise, or invalid data.
- **Conservative incident-window severity**, based on any observed
  threshold excursion, even if subsequent readings cool down.
- **A non-executable action category**, with invalid telemetry requiring
  sensor validation and a critical excursion requiring human review.

This separation prevents an apparently stable or cooling trend from
clearing a historical critical incident. Such a clearance would require
an independently governed, authenticated workflow, which is not
implemented. The risk reconciliation uses a bounded incident window,
not cross-session state, and its thresholds are simulation defaults,
not validated limits for any real equipment.

Importantly, suggesting thermal inspection for a historical
critical excursion is not automatically unsafe; the prior 4/9 result
reflects the strictly defined benchmark label, not an engineering
judgement on the real adequacy of those suggestions.

For now, the existing three-agent runtime remains unchanged. This
module is a tested conservative policy primitive; it does not add
hardware capabilities, approvals, or device actions.
