# Deterministic degraded mode

When Ollama fails, times out at the provider boundary or returns an invalid
proposal, the diagnostic CLI retains the Supervisor's **read-only**
recommendation. `governance_mode` becomes `deterministic_degraded` and
`model_accepted` becomes `false`.

This fallback does not pretend that a model inference succeeded, and does not
grant any authority to operate hardware. An invalid sensor reading still
requires review according to the supervisor rules. Production-grade timeout
enforcement, authorization and emergency handling are separate requirements.
