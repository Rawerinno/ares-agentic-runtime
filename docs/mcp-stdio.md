# ARES MCP stdio — simulation-only compatibility layer

This is a **limited** MCP stdio implementation for protocol version
`2025-06-18`. It implements initialize, initialized notification, ping,
tools/list, and tools/call, with a single read-only simulated sensor.
It is not an implementation of the newer 2026-07-28 stateless protocol,
nor a substitute for a fully vetted MCP SDK.

Launch locally:

```powershell
uv run python -m ares.integrations.mcp_stdio
```

The invoking MCP client starts this process and exchanges one JSON-RPC message
per newline on stdin/stdout. Nothing is sent over the network.

The client cannot select the agent identity or define arbitrary device tools.
The server uses a fixed, locally configured simulated identity and grant.
No external telemetry, physical devices, write operations or dynamic commands
are exposed. Do not expose this process to an untrusted remote client.

## Out of scope

Production authentication, multi-tenant identity, approvals, network transports,
2026 MCP compliance, concurrent execution, event persistence and hardware control.
These require separate security and compatibility reviews.
