"""Role-specific structured localhost Ollama transport for three governed agents.

The model returns a JSON object, not a JSON-encoded string embedded in
an `answer` property. Outputs remain entirely untrusted until the ARES
governor validates them. No tools, approval or actuation are exposed.
"""

import json
from collections.abc import Callable
from typing import cast

from ares.intelligence.ollama_transport import OllamaLocalTransport
from ares.intelligence.transport import RequestLimits


def ollama_three_role_generator(
    model: str, *, timeout: float = 30.0, role_only: bool = False
) -> Callable[[str], str]:
    """Create strictly local, bounded role-specific JSON generation."""
    if not model.strip() or len(model) > 120:
        raise ValueError("model must have 1..120 nonblank characters")
    limits = RequestLimits(timeout_seconds=timeout, max_response_bytes=8192)
    transport = OllamaLocalTransport()
    role_fields = {
        "investigator": ("hypothesis", ("stable", "thermal_load", "sensor_fault")),
        "planner": ("plan", ("monitor", "inspect", "human_review")),
        "critic": ("verdict", ("consistent", "inconsistent")),
    }

    def generate(question: str) -> str:
        role = question.split("ROLE=", 1)[1].split(".", 1)[0]
        if role not in role_fields:
            raise ValueError("unsupported LLM role")
        field, values = role_fields[role]
        properties: dict[str, object] = {field: {"type": "string", "enum": list(values)}}
        required = [field]
        if not role_only:
            properties["severity"] = {
                "type": "string",
                "enum": ["normal", "warning", "critical"],
            }
            required.append("severity")
        schema: dict[str, object] = {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }
        # The local 3B model frequently confuses healthy telemetry with a sensor
        # fault. Give it bounded interpretation examples, not an answer for the
        # current scenario. The deterministic governor still validates outputs.
        role_guidance = (
            (
                "Investigator decision order: first inspect trusted healthy and "
                "temperature_c. sensor_fault ONLY if healthy is false or "
                "temperature_c is null/non-finite. If healthy is true and the "
            "temperature is finite, NEVER select sensor_fault: use stable for "
                "normal severity and thermal_load for warning or critical severity. "
                "Examples: {healthy:true,temperature_c:18,severity:normal} => stable; "
                "{healthy:true,temperature_c:65,severity:warning} => thermal_load; "
                "{healthy:true,temperature_c:95,severity:critical} => thermal_load; "
                "{healthy:false,temperature_c:null,severity:critical} => sensor_fault. "
            )
            if role == "investigator"
            else ""
        )
        payload = {
            "model": model,
            "prompt": (
                "You are an untrusted, read-only engineering analyst. "
                "Return exactly one JSON object with the required field(s): "
                + (field if role_only else f"{field} and severity")
                + ". Do not use Markdown or an answer wrapper. "
                "The supplied telemetry is authoritative. "
                + role_guidance
                + "No external tools or equipment commands are permitted.\n"
                + question
            ),
            "stream": False,
            "think": False,
            "format": schema,
            "options": {"temperature": 0, "num_predict": 128},
        }
        response = transport.request(json.dumps(payload).encode("utf-8"), limits=limits)
        envelope: object = json.loads(response)
        if not isinstance(envelope, dict):
            raise ValueError("ollama_invalid_envelope")
        answer = cast("dict[str, object]", envelope).get("response")
        if not isinstance(answer, str) or len(answer) > 512:
            raise ValueError("ollama_invalid_content")
        decoded: object = json.loads(answer)
        if not isinstance(decoded, dict):
            raise ValueError("ollama_invalid_object")
        # No semantic acceptance here: the deterministic governor owns validation.
        return json.dumps(decoded, separators=(",", ":"), ensure_ascii=True)

    return generate
