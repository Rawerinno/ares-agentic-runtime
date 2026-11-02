"""Role-specific structured localhost Ollama calls for the governed team.

Ollama produces the role JSON object directly, not a nested answer string.
The deterministic three-agent governor still validates every proposed field.
"""

import json
from typing import cast

from ares.intelligence.ollama_transport import OllamaLocalTransport
from ares.intelligence.transport import RequestLimits
from ares.runtime.governed_three_agents import GovernedThreeAgentTeam


def ollama_three_role_generator(model: str, *, timeout: float = 30.0) -> str:
    """Deprecated placeholder to retain no implicit network calls."""
    raise NotImplementedError
