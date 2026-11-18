"""Tests for P1.3: Model Context Protocol (MCP) Lifecycle, Handshake, Schema Validation, and Isolation."""

from __future__ import annotations

import pytest

from app.tools.mcp.mcp_client import (
    DEFAULT_MCP_SERVERS,
    build_isolated_mcp_env,
    mcp_client_manager,
)


@pytest.fixture(autouse=True)
def clean_mcp():
    mcp_client_manager.clear_mock_handlers()
    # Reset all servers to disabled
    for s in mcp_client_manager.list_servers():
        s.enabled = False
    yield
    mcp_client_manager.clear_mock_handlers()
    for s in mcp_client_manager.list_servers():
        s.enabled = False


def test_default_servers_are_pinned_and_disabled_by_default():
    """Verify all default MCP servers are pinned with exact versions and disabled by default."""
    for s in DEFAULT_MCP_SERVERS:
        assert s.enabled is False
        assert s.package_version != ""
        assert "@" in s.args[-1] or "==" in s.args[-1]
        assert s.publisher != ""
        assert s.source == "official"


def test_isolated_mcp_env_scrubs_secrets(monkeypatch):
    """Verify build_isolated_mcp_env strips all secret keys from subprocess environment."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-12345")
    monkeypatch.setenv("ANTHROPIC_SECRET", "super-secret")
    monkeypatch.setenv("AKSA_AUTH_TOKEN", "aksa-token-999")
    monkeypatch.setenv("SYSTEMROOT", "C:\\Windows")

    env = build_isolated_mcp_env()
    assert "OPENAI_API_KEY" not in env
    assert "ANTHROPIC_SECRET" not in env
    assert "AKSA_AUTH_TOKEN" not in env
    # Allowed system variables are retained
    if "SYSTEMROOT" in env:
        assert env["SYSTEMROOT"] == "C:\\Windows"


@pytest.mark.asyncio
async def test_tool_invocation_rejected_when_server_disabled():
    """Verify invoke_mcp_tool fails closed when the target server is disabled."""
    res = await mcp_client_manager.invoke_mcp_tool(
        server_id="mcp_filesystem",
        tool_name="list_directory",
        arguments={"path": "."},
    )
    assert res.success is False
    assert res.data["status"] == "disabled"
    assert "nonaktif" in res.summary


@pytest.mark.asyncio
async def test_tool_not_found_in_discovered_tools():
    """Verify calling an unregistered tool on an enabled server returns tool_not_found."""
    mcp_client_manager.toggle_server("mcp_filesystem", enabled=True)

    res = await mcp_client_manager.invoke_mcp_tool(
        server_id="mcp_filesystem",
        tool_name="arbitrary_unregistered_tool",
    )
    assert res.success is False
    assert res.data["status"] == "tool_not_found"
    assert "tidak terdaftar" in res.summary


@pytest.mark.asyncio
async def test_payload_size_limit_guard():
    """Verify payload larger than MAX_PAYLOAD_SIZE is rejected immediately."""
    mcp_client_manager.toggle_server("mcp_filesystem", enabled=True)
    huge_data = {"data": "X" * (11 * 1024 * 1024)}  # 11 MB

    res = await mcp_client_manager.invoke_mcp_tool(
        server_id="mcp_filesystem",
        tool_name="write_file",
        arguments=huge_data,
    )
    assert res.success is False
    assert res.data["status"] == "payload_too_large"
    assert "melebihi batas aman" in res.summary


@pytest.mark.asyncio
async def test_successful_mock_invocation():
    """Verify tool execution via registered mock handler succeeds with structured response."""
    mcp_client_manager.toggle_server("mcp_sqlite", enabled=True)

    def mock_sqlite(tool_name: str, args: dict | None):
        if tool_name == "list_tables":
            return {"tables": ["users", "orders", "inventory"]}
        return {"error": "unsupported"}

    mcp_client_manager.set_mock_handler("mcp_sqlite", mock_sqlite)

    res = await mcp_client_manager.invoke_mcp_tool(
        server_id="mcp_sqlite",
        tool_name="list_tables",
    )
    assert res.success is True
    assert res.data["status"] == "succeeded"
    assert res.data["result"]["tables"] == ["users", "orders", "inventory"]


@pytest.mark.asyncio
async def test_rpc_error_handling():
    """Verify MCP protocol error is properly propagated and reported."""
    mcp_client_manager.toggle_server("mcp_sqlite", enabled=True)

    def mock_error(tool_name: str, args: dict | None):
        return {"error": {"code": -32602, "message": "Invalid query parameters"}}

    mcp_client_manager.set_mock_handler("mcp_sqlite", mock_error)

    res = await mcp_client_manager.invoke_mcp_tool(
        server_id="mcp_sqlite",
        tool_name="read_query",
    )
    assert res.success is False
    assert res.data["status"] == "rpc_error"
    assert "Invalid query parameters" in str(res.data["error"])


@pytest.mark.asyncio
async def test_schema_validation_and_argument_mismatch():
    """Verify tool execution fails closed if arguments mismatch registered schema (P1-02)."""
    mcp_client_manager.toggle_server("mcp_filesystem", enabled=True)
    server = mcp_client_manager.get_server("mcp_filesystem")
    assert server is not None

    # Inject schema for read_file: requires 'path' as string
    server.tool_schemas["read_file"] = {
        "type": "object",
        "required": ["path"],
        "properties": {
            "path": {"type": "string"},
            "offset": {"type": "integer"},
        },
    }

    # 1. Missing required parameter 'path'
    res_missing = await mcp_client_manager.invoke_mcp_tool(
        server_id="mcp_filesystem",
        tool_name="read_file",
        arguments={"offset": 0},
    )
    assert res_missing.success is False
    assert res_missing.data["status"] == "schema_validation_failed"
    assert "Parameter wajib 'path' tidak disediakan" in res_missing.summary

    # 2. Invalid property type: integer expected for offset, got string
    res_type = await mcp_client_manager.invoke_mcp_tool(
        server_id="mcp_filesystem",
        tool_name="read_file",
        arguments={"path": "/valid/path.txt", "offset": "not_an_int"},
    )
    assert res_type.success is False
    assert res_type.data["status"] == "schema_validation_failed"
    assert "Tipe parameter 'offset' tidak valid" in res_type.summary


@pytest.mark.asyncio
async def test_handshake_failure_and_timeout():
    """Verify handshake failure and timeout handling (P1-02)."""
    mcp_client_manager.toggle_server("mcp_playwright", enabled=True)

    # Mock subprocess communication timeout
    with pytest.raises(TimeoutError):
        # discover_tools with unreachable mock or 0.001 timeout
        await mcp_client_manager.discover_tools("mcp_playwright", timeout=0.0001)


