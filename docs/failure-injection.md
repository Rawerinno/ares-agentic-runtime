# Offline fault-injection evaluation

`failure_matrix()` evaluates a simulated critical sensor reading against
malformed output, missing keys, severity spoofing, unsafe downgrading,
oversized responses, provider exceptions and a valid critical recommendation.

The harness never calls Ollama, the network or real hardware. It checks that
invalid proposals do not produce a decision and cannot reach governance.
It does not test network timeouts, slow responses or hardware-specific safety.

The first live benchmark on the Lenovo Slim (Llama 3.2 3B, three cycles of six
scenarios) returned 6/18 raw correct recommendations and 18/18 governed
recommendations, with no model errors or rejections. Those are observed
results, not claims of model accuracy outside the six fixed scenarios.
