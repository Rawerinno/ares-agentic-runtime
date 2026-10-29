# ARES + Ollama (local provider)

The adapter uses Ollama's documented `POST /api/generate` endpoint with
`stream: false`, a JSON Schema in `format`, and a bounded token request.
The generated JSON is **untrusted** and remains subject to `ProposalEngine`
validation. It has no tool-calling or hardware permissions.

## Local prerequisites

1. Install Ollama from https://ollama.com/download and start its local service.
2. In PowerShell run `ollama pull llama3.2:3b`. This is an example model, not a
   guarantee of high diagnostic accuracy or that it fits every computer.
3. Confirm the service is available at `http://127.0.0.1:11434`.

To use the adapter in Python:

```python
from ares.intelligence.decisions import ProposalEngine
from ares.intelligence.ollama import OllamaAdapter
from ares.intelligence.ollama_transport import OllamaLocalTransport
from ares.intelligence.transport import ProviderClient, RequestLimits

limits = RequestLimits(timeout_seconds=30, max_response_bytes=16384)
adapter = OllamaAdapter(ProviderClient(OllamaLocalTransport(), limits), "llama3.2:3b")
engine = ProposalEngine(adapter)
# engine.propose(assessment) when a trusted Supervisor assessment exists.
```

The HTTP host is restricted to a numeric loopback address. Redirects are
rejected. Socket timeout is not an absolute end-to-end deadline. Local model
availability, throughput and real-world quality have **not** yet been verified.
No real device commands or approval bypass are supported.

Run offline tests: `uv run pytest tests/intelligence/test_ollama.py -v`.
