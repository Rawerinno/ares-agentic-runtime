"""Ollama ModelAdapter: local generation of untrusted proposal JSON."""

import json
from typing import cast

from ares.intelligence.transport import ProviderClient
from ares.supervisor import Assessment


class OllamaAdapter:
    """Construct a fixed, proposal-only request to Ollama's generate endpoint."""

    def __init__(self, client: ProviderClient, model: str) -> None:
        if not model.strip() or len(model) > 120:
            raise ValueError("Ollama model name must be 1..120 nonblank characters")
        self._client = client
        self._model = model

    def propose(self, assessment: Assessment) -> object:
        """Return untrusted JSON for validation by ProposalEngine."""
        schema: dict[str, object] = {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["observe", "investigate", "request_review"]},
                "rationale": {"type": "string", "maxLength": 1000},
                "assessment_severity": {
                    "type": "string",
                    "enum": ["normal", "warning", "critical"],
                },
            },
            "required": ["kind", "rationale", "assessment_severity"],
            "additionalProperties": False,
        }
        prompt = (
            "You are a diagnostic recommendation assistant. "
            "Return ONLY JSON. Do not suggest commands, actuators or direct actions. "
            "Never change severity. Critical must request_review; warning must not observe. "
            f"Measured temperature C: {assessment.snapshot.temperature_c}. "
            f"Sensor healthy: {assessment.snapshot.healthy}. "
            f"Severity: {assessment.severity.value}. "
            f"Reason: {assessment.reason}. "
            "Propose a safe observation or human investigation."
        )
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "format": schema,
            "options": {"temperature": 0, "num_predict": 256},
        }
        response_bytes = self._client.request(json.dumps(payload).encode("utf-8"))
        try:
            envelope: object = json.loads(response_bytes)
            if not isinstance(envelope, dict):
                raise ValueError("Invalid Ollama envelope")
            content = cast("dict[str, object]", envelope).get("response")
            if not isinstance(content, str):
                raise ValueError("Missing Ollama response")
            return json.loads(content)
        except (UnicodeDecodeError, ValueError, TypeError) as exc:
            raise ValueError("ollama_invalid_response") from exc
