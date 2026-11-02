"""Local, bounded investigator follow-up proposals about temporal evidence.

Generated text cannot change the evidence state or authorize device actions.
"""

import json
from collections.abc import Callable
from typing import cast

from ares.intelligence.ollama_transport import OllamaLocalTransport
from ares.intelligence.transport import RequestLimits
from ares.runtime.temporal_evidence import EvidenceReport

FOLLOWUPS = (
    "validate_sensor",
    "collect_more_samples",
    "inspect_thermal_system",
    "continue_monitoring",
)


def reference_followup(report: EvidenceReport) -> str:
    """Deterministic reference (not a language model)."""
    return json.dumps({"followup": report.suggested_followup})



def bounded_followup(answer: str) -> str:
    """Extract only an allowlisted model value; never return model prose."""
    if len(answer) > 256:
        return "unrecognized"
    try:
        raw: object = json.loads(answer)
    except (ValueError, TypeError):
        return "unrecognized"
    if not isinstance(raw, dict):
        return "unrecognized"
    value = cast("dict[str, object]", raw).get("followup")
    return value if type(value) is str and value in FOLLOWUPS else "unrecognized"


def parse_followup(answer: str, report: EvidenceReport) -> tuple[bool, str]:
    """Validate untrusted proposal, exposing only finite allowlisted categories."""
    if len(answer) > 256:
        return False, "oversized"
    try:
        data: object = json.loads(answer)
    except (ValueError, TypeError):
        return False, "invalid_json"
    if not isinstance(data, dict):
        return False, "invalid_shape"
    proposal = cast("dict[str, object]", data)
    if set(proposal) != {"followup"}:
        return False, "invalid_fields"
    value = proposal["followup"]
    if type(value) is not str or value not in FOLLOWUPS:
        return False, "invalid_value"
    return (True, "accepted") if value == report.suggested_followup else (False, "policy_mismatch")


def ollama_evidence_generator(
    model: str, *, timeout: float = 30.0
) -> Callable[[EvidenceReport], str]:
    """Use a local model for advisory follow-up; no tools or writes exposed."""
    if not model.strip() or len(model) > 120:
        raise ValueError("model must have 1..120 nonblank characters")
    transport = OllamaLocalTransport()
    limits = RequestLimits(timeout_seconds=timeout, max_response_bytes=8192)
    schema = {
        "type": "object",
        "properties": {"followup": {"type": "string", "enum": list(FOLLOWUPS)}},
        "required": ["followup"],
        "additionalProperties": False,
    }

    def generate(report: EvidenceReport) -> str:
        context = {
            "evidence_state": report.state.value,
            "sample_count": report.sample_count,
            "valid_count": report.valid_count,
            "delta_c": report.delta_c,
            "highest_c": report.highest_c,
        }
        prompt = (
            "You are an investigation assistant with no tool permissions. "
            "Select exactly one safe follow-up for the observed evidence. "
            "Invalid telemetry => validate_sensor. Fewer than three valid samples "
            "=> collect_more_samples. Confirmed rising temperature => "
            "inspect_thermal_system. Otherwise => continue_monitoring. "
            "A temperature value alone never proves a physical root cause. "
            "Return only a JSON object with the followup key. "
            "Authoritative evidence: " + json.dumps(context, allow_nan=False)
        )
        payload = {
            "model": model,
            "prompt": prompt,
            "format": schema,
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_predict": 80},
        }
        response = transport.request(json.dumps(payload).encode("utf-8"), limits=limits)
        envelope: object = json.loads(response)
        if not isinstance(envelope, dict):
            raise ValueError("invalid_model_envelope")
        value = cast("dict[str, object]", envelope).get("response")
        if not isinstance(value, str) or len(value) > 512:
            raise ValueError("invalid_model_content")
        return value

    return generate
