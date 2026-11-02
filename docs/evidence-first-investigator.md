# Evidence-first Investigator — experimental

The first V5 audit showed a strong, unhelpful `sensor_fault` bias in the
current Llama 3.2:3B Investigator. In nine isolated probes it proposed
`sensor_fault` seven times when the synthetic label was not a sensor
fault; only three investigator responses passed. The deterministic
supervisor remained correct in all nine simulated cases. Planner and
Critic each passed nine isolated probes.

**A single valid high temperature is not proof of thermal overload.**
The previous benchmark's `thermal_load` hypothesis is a synthetic label,
not a substantiated physical root cause. To establish a more defensible
boundary we added a separate evidence-first workflow:

- One or two valid samples: `insufficient_history`
- Three or more valid samples increasing monotonically by a configurable
  threshold: `rising_temperature` (an observation, not a cause)
- Other valid histories: `no_confirmed_rise`
- Any unhealthy/nonfinite sample: `invalid_telemetry`

The LLM may only suggest one of four bounded **manual follow-ups**:
`validate_sensor`, `collect_more_samples`, `inspect_thermal_system`,
or `continue_monitoring`. Python validates the answer against trusted
evidence, never adopts model conclusions as safety authority, and never
authorizes an actuator. This is a separate experimental evaluation and
does not yet replace the existing three-agent incident workflow.

Offline acceptance:

```powershell
uv run python -m ares.runtime.evidence_acceptance --output ares-evidence-offline.json
```

Local Llama acceptance:

```powershell
uv run python -m ares.runtime.evidence_acceptance --live --model llama3.2:3b --output ares-evidence-live.json
```

Both run nine synthetic scenarios. The report separates the correctness
of evidence classifications from the LLM's rate of valid suggestions,
and redacts arbitrary model output. This does not establish reliability
on real devices or measurements.

## Diagnostic follow-up confusion

The first live evidence benchmark classified all nine synthetic histories with deterministic rules, but accepted only four of nine Llama follow-ups. Three no-rise and two invalid-telemetry cases were rejected; the original report did not show which allowable action the model selected. The updated evaluator records `bounded_proposal` per case and `followup_confusion`, a table of trusted recommended follow-up versus the model's allowlisted category. Unknown or malformed model strings become `unrecognized`, exceptions become `no_response`, and arbitrary model text is not stored. This is observational diagnostic data, not model-granted authority.

## Independent incident-window risk in acceptance reports

The evidence acceptance CLI now records the conservative `risk_severity`, `risk_reason` and `risk_action` in each synthetic scenario. Risk is calculated independently of the model's candidate `followup` and of the evidence-state follow-up benchmark. Aggregate `risk_counts` show how often an incident window reaches each simulated threshold. For example, a cooling trace following 85°C remains critical, and a flat 60°C trace remains warning despite lacking a rising trend. The new fields do not constitute hardware certification or any permission to operate a device. Historical risk has only the bounded scope of supplied readings; cross-session persistence and authorized clearance are still future work.
