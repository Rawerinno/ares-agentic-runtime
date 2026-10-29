# Diagnostic quality scorecard

The demo exposes four explicit quality indicators: valid governed action
category, evidence availability, agreement with the model recommendation,
and whether natural-language claims have been independently verified.

`free_text_verified` is intentionally always `false` in this phase: no
automated technical fact checker or validated equipment reference database
exists. This is **not** an overall accuracy percentage, root-cause proof or
safety certification. A model can agree with the supervisor and still give a
misleading narrative.

For the local Ollama smoke test:

```powershell
uv run python -m ares.intelligence.ollama_demo --live --temperature 85
```

Inspect the `quality` object and `audit_digest` in the JSON result.
