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
        # The trusted supervisor decides severity; the model only explains that decision.
        # Unambiguous escalation rules reduce unnecessary human-review recommendations.
        expected_kind = {
            "normal": "observe",
            "warning": "investigate",
            "critical": "request_review",
        }[assessment.severity.value]
        prompt = (
            "You are a diagnostic assistant, NOT an equipment controller. "
            "Return only JSON matching the schema. "
            "The measured severity is authoritative; do not change it. "
            "Recommendation policy: normal -> observe, warning -> investigate, "
            "critical -> request_review. "
            "Never escalate a normal or warning measurement to request_review "
            "without a separate documented reason, which this input does not provide. "
            "Never generate hardware instructions or actuator commands. "
            f"Authoritative recommendation kind: {expected_kind}. "
            f"Temperature Celsius: {assessment.snapshot.temperature_c}. "
            f"Healthy sensor: {assessment.snapshot.healthy}. "
            f"Authoritative severity: {assessment.severity.value}. "
            f"Reason: {assessment.reason}. "
            "Supply a brief rationale consistent with the authoritative classification."
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
