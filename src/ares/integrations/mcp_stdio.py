"""Minimal, simulation-only MCP stdio server (protocol 2025-06-18).

No network listener, hardware writes, caller-supplied agent identity or external
tool handlers. This is intentionally a narrow subset, not a general MCP SDK.
"""

import json
import sys
from typing import Any, TextIO, cast

from ares.integrations import ReadOnlyToolGateway
from ares.safety import AuthorizationError, Capability, Policy
from ares.simulation import DeviceSimulator

PROTOCOL_VERSION = "2025-06-18"
TOOL_NAME = "ares_read_temperature"


def make_gateway() -> ReadOnlyToolGateway:
    """Build a simulation-only gateway with a fixed local identity."""
    gateway = ReadOnlyToolGateway(
        Policy(frozenset({("local-simulator-client", TOOL_NAME, Capability.READ)}))
    )
    gateway.register_sensor(TOOL_NAME, DeviceSimulator("simulated-temperature"))
    return gateway


class StdioMCPServer:
    """Handle a narrow MCP request subset with explicit lifecycle checks."""

    def __init__(self, gateway: ReadOnlyToolGateway) -> None:
        self.gateway = gateway
        self.initialized = False
        self.ready = False

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Return a JSON-RPC response or None for a notification."""
        identifier = message.get("id")
        if message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
            return self.error_response(identifier, -32600, "Invalid Request")
        method: str = message["method"]
        if method == "notifications/initialized" and "id" not in message:
            if self.initialized:
                self.ready = True
            return None
        if "id" not in message:
            return None
        if method == "initialize":
            if self.initialized:
                return self.error_response(identifier, -32600, "Already initialized")
            params = message.get("params")
            if (
                not isinstance(params, dict)
                or cast("dict[str, object]", params).get("protocolVersion") != PROTOCOL_VERSION
            ):
                return self.error_response(identifier, -32602, "Unsupported protocol version")
            self.initialized = True
            return self._success(
                identifier,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "ares-simulator", "version": "0.0.1"},
                },
            )
        if not self.ready:
            return self.error_response(identifier, -32000, "Server not initialized")
        if method == "ping":
            return self._success(identifier, {})
        if method == "tools/list":
            return self._success(
                identifier,
                {
                    "tools": [
                        {
                            "name": TOOL_NAME,
                            "description": "Read a simulated temperature sensor (read-only)",
                            "inputSchema": {
                                "type": "object",
                                "properties": {},
                                "additionalProperties": False,
                            },
                        }
                    ]
                },
            )
        if method == "tools/call":
            params = message.get("params")
            parsed = cast("dict[str, object]", params) if isinstance(params, dict) else {}
            if (
                not isinstance(params, dict)
                or parsed.get("name") != TOOL_NAME
                or parsed.get("arguments", {}) != {}
            ):
                return self.error_response(identifier, -32602, "Invalid tool call")
            try:
                reading = self.gateway.read_sensor(
                    agent_id="local-simulator-client", tool_id=TOOL_NAME
                )
            except (AuthorizationError, LookupError, RuntimeError) as exc:
                return self._success(
                    identifier,
                    {"content": [{"type": "text", "text": str(exc)}], "isError": True},
                )
            snap = reading.snapshot
            return self._success(
                identifier,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "device_id": snap.device_id,
                                    "step": snap.step,
                                    "temperature_c": snap.temperature_c,
                                    "healthy": snap.healthy,
                                }
                            ),
                        }
                    ],
                    "isError": False,
                },
            )
        return self.error_response(identifier, -32601, "Method not found")

    @staticmethod
    def _success(identifier: object, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": identifier, "result": result}

    @staticmethod
    def error_response(identifier: object, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": identifier,
            "error": {"code": code, "message": message},
        }


def serve(stdin: TextIO, stdout: TextIO) -> None:
    """Serve newline-delimited JSON-RPC without emitting log text to stdout."""
    server = StdioMCPServer(make_gateway())
    for line in stdin:
        try:
            message: object = json.loads(line)
        except json.JSONDecodeError:
            response = StdioMCPServer.error_response(None, -32700, "Parse error")
        else:
            if not isinstance(message, dict):
                response = StdioMCPServer.error_response(None, -32600, "Invalid Request")
            else:
                response = server.handle(cast("dict[str, Any]", message))
        if response is not None:
            stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            stdout.flush()


def main() -> None:
    serve(sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
