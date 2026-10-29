# Provider transport contract

The runtime now defines a provider-neutral transport seam with explicit
request timeout and maximum response size settings. A fake transport tests
success, failure redaction and output size validation.

**Important:** The injected transport is responsible for enforcing the actual
request deadline and response byte limit during I/O. The wrapper only checks
the resulting response size. No production HTTP transport exists yet, and the
contract does not provide cancellation for a blocked transport.

This module must not be described as a complete network security boundary.
External API keys, networking and billing remain disabled. Never commit secrets.
