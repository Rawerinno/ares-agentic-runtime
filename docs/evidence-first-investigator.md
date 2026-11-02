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
