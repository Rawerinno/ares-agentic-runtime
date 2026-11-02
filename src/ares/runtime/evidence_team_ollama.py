"""Locally hosted, schema-constrained three-role evidence team transport."""

import json
from collections.abc import Callable
from typing import cast

from ares.intelligence.ollama_transport import OllamaLocalTransport
from ares.intelligence.transport import RequestLimits


def ollama_evidence_team_generator(
    model: str, *, timeout: float = 30.0
) -> Callable[[str], str]:
    """Make three independent read-only calls; return untrusted JSON for validation."""
    if not model.strip() or len(model) > 120:
        raise ValueError("model must contain 1..120 nonblank characters")
    transport = OllamaLocalTransport()
    limits = RequestLimits(timeout_seconds=timeout, max_response_bytes=8192)
    values = {
        "investigator": (
            "followup",
            ("validate_sensor", "collect_more_samples", "inspect_thermal_system",
             "continue_monitoring"),
        ),
        "planner": (
            "action",
            ("monitor", "collect_evidence", "inspect", "validate_sensor", "human_review"),
        ),
        "critic": ("verdict", ("consistent", "inconsistent")),
    }

    def generate(prompt: str) -> str:
        role = prompt.split("ROLE=", 1)[1].split(".", 1)[0]
        if role not in values:
            raise ValueError("unrecognized role")
        key, allowed = values[role]
        schema = {
            "type": "object",
            "properties": {key: {"type": "string", "enum": list(allowed)}},
            "required": [key],
            "additionalProperties": False,
        }
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "format": schema,
            "options": {"temperature": 0, "num_predict": 96},
        }
        raw = transport.request(json.dumps(payload).encode("utf-8"), limits=limits)
        envelope: object = json.loads(raw)
        if not isinstance(envelope, dict):
            raise ValueError("invalid model envelope")
        response = cast("dict[str, object]", envelope).get("response")
        if not isinstance(response, str) or len(response) > 512:
            raise ValueError("invalid model reply")
        return response

    return generate
