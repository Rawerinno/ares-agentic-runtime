"""Protocol tests for the local, read-only MCP stdio server."""

import io
import json
from typing import Any

from ares.integrations.mcp_stdio import PROTOCOL_VERSION, StdioMCPServer, make_gateway, serve


def request(identifier: int, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": identifier, "method": method, "params": params or {}}


def initialized_server() -> StdioMCPServer:
    server = StdioMCPServer(make_gateway())
    response = server.handle(request(1, "initialize", {"protocolVersion": PROTOCOL_VERSION}))
    assert response is not None
    server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
    return server


def test_handshake_and_read_tool() -> None:
    server = initialized_server()
    listing = server.handle(request(2, "tools/list"))
    assert listing is not None
    assert listing["result"]["tools"][0]["name"] == "ares_read_temperature"
    result = server.handle(
        request(3, "tools/call", {"name": "ares_read_temperature", "arguments": {}})
    )
    assert result is not None
    assert result["result"]["isError"] is False
    assert json.loads(result["result"]["content"][0]["text"])["temperature_c"] == 20.0


def test_no_tool_use_before_initialized_notification() -> None:
    server = StdioMCPServer(make_gateway())
    assert server.handle(request(1, "tools/list"))["error"]["code"] == -32000  # type: ignore[index]
    server.handle(request(2, "initialize", {"protocolVersion": PROTOCOL_VERSION}))
    assert server.handle(request(3, "tools/list"))["error"]["code"] == -32000  # type: ignore[index]


def test_unsupported_protocol_rejected() -> None:
    response = StdioMCPServer(make_gateway()).handle(
        request(1, "initialize", {"protocolVersion": "unsupported"})
    )
    assert response is not None
    assert response["error"]["code"] == -32602


def test_no_write_tool_is_exposed() -> None:
    server = initialized_server()
    response = server.handle(request(2, "tools/call", {"name": "write_device"}))
    assert response is not None
    assert response["error"]["code"] == -32602


def test_invalid_arguments_rejected() -> None:
    server = initialized_server()
    response = server.handle(
        request(2, "tools/call", {"name": "ares_read_temperature", "arguments": {"step": 5}})
    )
    assert response is not None
    assert response["error"]["code"] == -32602


def test_ping_and_unknown_method() -> None:
    server = initialized_server()
    assert server.handle(request(1, "ping"))["result"] == {}  # type: ignore[index]
    assert server.handle(request(2, "missing"))["error"]["code"] == -32601  # type: ignore[index]


def test_duplicate_initialization_rejected() -> None:
    server = initialized_server()
    result = server.handle(request(2, "initialize", {"protocolVersion": PROTOCOL_VERSION}))
    assert result is not None
    assert result["error"]["code"] == -32600


def test_invalid_message_and_notification() -> None:
    server = initialized_server()
    result = server.handle({"jsonrpc": "1.0", "id": 2, "method": "ping"})
    assert result is not None
    assert result["error"]["code"] == -32600
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_stdio_wire_format_and_parse_errors() -> None:
    messages = [
        "{broken",
        json.dumps(request(1, "initialize", {"protocolVersion": PROTOCOL_VERSION})),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        json.dumps(request(2, "tools/list")),
        json.dumps(request(3, "tools/call", {"name": "ares_read_temperature", "arguments": {}})),
        "[]",
    ]
    output = io.StringIO()
    serve(io.StringIO("\n".join(messages) + "\n"), output)
    responses = [json.loads(line) for line in output.getvalue().splitlines()]
    assert len(responses) == 5
    assert responses[0]["error"]["code"] == -32700
    assert responses[3]["result"]["isError"] is False
    assert responses[4]["error"]["code"] == -32600
