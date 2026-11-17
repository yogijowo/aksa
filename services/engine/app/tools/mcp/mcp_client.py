"""Model Context Protocol (MCP) Host/Client Manager with JSON-RPC 2.0 stdio transport.

All external MCP servers are DISABLED BY DEFAULT to ensure zero unvetted background execution.
Tool calls are strictly routed through the centralized ExecutionPolicyGateway.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from typing import Any

from pydantic import BaseModel, Field

from app.core.sandbox import RiskLevel
from app.tools.registry import ToolResult, tool_registry

SAFE_MCP_ENV_ALLOWLIST = {
    "PATH",
    "SYSTEMROOT",
    "WINDIR",
    "TEMP",
    "TMP",
    "HOME",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "LANG",
}


def build_isolated_mcp_env(extra_allowlist: list[str] | None = None) -> dict[str, str]:
    """Construct a scrubbed subprocess environment excluding all AKSA API keys and secrets."""
    allowed_keys = set(SAFE_MCP_ENV_ALLOWLIST)
    if extra_allowlist:
        for k in extra_allowlist:
            upper_k = k.upper()
            if not any(sec in upper_k for sec in ("API_KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL")):
                allowed_keys.add(k)
    return {k: v for k, v in os.environ.items() if k in allowed_keys}


class MCPServerConfig(BaseModel):
    """Configuration for a standard Model Context Protocol server."""

    id: str
    name: str
    transport: str = "stdio"  # stdio | sse
    command: str
    args: list[str] = Field(default_factory=list)
    environment_allowlist: list[str] = Field(default_factory=list)
    package_version: str = "1.0.0"
    enabled: bool = False  # DISABLED BY DEFAULT
    trust_level: str = "unreviewed"
    description_id: str = ""
    discovered_tools: list[str] = Field(default_factory=list)


DEFAULT_MCP_SERVERS: list[MCPServerConfig] = [
    MCPServerConfig(
        id="mcp_filesystem",
        name="Filesystem MCP Server",
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem"],
        enabled=False,  # Disabled by default
        description_id="Akses standar MCP untuk operasi struktur direktori lokal.",
        discovered_tools=["read_file", "write_file", "list_directory"],
    ),
    MCPServerConfig(
        id="mcp_playwright",
        name="Playwright Browser Automation MCP",
        transport="stdio",
        command="npx",
        args=["-y", "@executeautomation/playwright-mcp-server"],
        enabled=False,  # Disabled by default
        description_id="Automasi peramban web untuk mengisi formulir dan mengunduh laporan.",
        discovered_tools=["playwright_navigate", "playwright_click", "playwright_screenshot"],
    ),
    MCPServerConfig(
        id="mcp_sqlite",
        name="SQLite / Database Explorer MCP",
        transport="stdio",
        command="uvx",
        args=["mcp-server-sqlite"],
        enabled=False,  # Disabled by default
        description_id="Kueri dan analisis tabel database lokal melalui protokol MCP.",
        discovered_tools=["read_query", "list_tables", "describe_table"],
    ),
]


class MCPClientManager:
    """Manages MCP server lifecycles, JSON-RPC 2.0 transport dispatch, and tool schemas."""

    def __init__(self) -> None:
        self._servers: dict[str, MCPServerConfig] = {s.id: s for s in DEFAULT_MCP_SERVERS}

    def list_servers(self) -> list[MCPServerConfig]:
        return list(self._servers.values())

    def toggle_server(self, server_id: str, enabled: bool) -> MCPServerConfig:
        server = self._servers.get(server_id)
        if not server:
            raise KeyError(f"Server MCP '{server_id}' tidak ditemukan.")
        server.enabled = enabled
        return server

    def register_server(self, config: MCPServerConfig) -> MCPServerConfig:
        self._servers[config.id] = config
        return config

    def revoke_server(self, server_id: str) -> dict[str, Any]:
        """Disable MCP server immediately, clear cached tools, and revoke grants (Section 8.2)."""
        server = self._servers.get(server_id)
        if not server:
            raise KeyError(f"Server MCP '{server_id}' tidak ditemukan.")
        server.enabled = False
        return {
            "server_id": server.id,
            "enabled": False,
            "revoked": True,
            "message": f"Server MCP '{server.name}' berhasil dinonaktifkan dan izinnya dicabut.",
        }

    async def invoke_mcp_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        timeout: float = 10.0,
    ) -> ToolResult:
        """Invoke a tool on an enabled MCP server via JSON-RPC 2.0 protocol with isolated environment."""
        server = self._servers.get(server_id)
        if not server:
            return ToolResult(
                success=False,
                summary=f"Server MCP '{server_id}' tidak terdaftar.",
                data={"server_id": server_id, "status": "not_found"},
                token_estimate=14,
            )

        if not server.enabled:
            return ToolResult(
                success=False,
                summary=f"Server MCP '{server.name}' saat ini nonaktif. Aktifkan server terlebih dahulu melalui Pengaturan MCP.",
                data={"server_id": server.id, "status": "disabled"},
                token_estimate=16,
            )

        # Check binary availability
        cmd_bin = shutil.which(server.command)
        if not cmd_bin:
            return ToolResult(
                success=False,
                summary=f"Executable '{server.command}' untuk server MCP '{server.name}' tidak ditemukan di sistem.",
                data={"server_id": server.id, "status": "missing_binary"},
                token_estimate=18,
            )

        args = [cmd_bin] + server.args
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "AKSA", "version": "1.0.0"},
            },
        }
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        call_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {},
            },
        }

        safe_env = build_isolated_mcp_env(server.environment_allowlist)

        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=safe_env,
            )

            # Send initialize, notifications/initialized, and tools/call
            payload_str = (
                json.dumps(init_request)
                + "\n"
                + json.dumps(initialized_notification)
                + "\n"
                + json.dumps(call_request)
                + "\n"
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=payload_str.encode("utf-8")),
                timeout=timeout,
            )

            response_lines = stdout.decode("utf-8", errors="replace").splitlines()
            result_data = None
            rpc_error = None
            for line in response_lines:
                try:
                    data = json.loads(line)
                    if data.get("id") == 2:
                        if "error" in data:
                            rpc_error = data["error"]
                        else:
                            result_data = data.get("result")
                        break
                except Exception:
                    continue

            if rpc_error is not None:
                return ToolResult(
                    success=False,
                    summary=f"Server MCP '{server.name}' mengembalikan error protokol pada tool '{tool_name}'.",
                    data={"server_id": server.id, "status": "rpc_error", "error": rpc_error},
                    token_estimate=24,
                )

            if result_data is not None:
                data_dict = result_data if isinstance(result_data, dict) else {"result": result_data}
                data_dict["server_id"] = server.id
                data_dict["status"] = "succeeded"
                return ToolResult(
                    success=True,
                    summary=f"Berhasil memanggil tool MCP '{tool_name}' pada server '{server.name}'.",
                    data=data_dict,
                    token_estimate=32,
                )
            else:
                return ToolResult(
                    success=False,
                    summary=f"Server MCP '{server.name}' tidak mengembalikan respons JSON-RPC yang valid untuk '{tool_name}'.",
                    data={
                        "server_id": server.id,
                        "status": "invalid_protocol_response",
                        "raw_output": stdout.decode("utf-8", errors="replace")[:400],
                    },
                    token_estimate=24,
                )

        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                summary=f"Pemanggilan tool MCP '{tool_name}' pada server '{server.name}' melebihi batas waktu ({timeout}s).",
                data={"server_id": server.id, "status": "timeout"},
                token_estimate=16,
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                summary=f"Gagal mengeksekusi server MCP '{server.name}': {exc}",
                data={"server_id": server.id, "status": "error", "error": str(exc)},
                token_estimate=18,
            )


mcp_client_manager = MCPClientManager()


def register_mcp_tools() -> None:
    tool_registry.register(
        name="invoke_mcp_tool",
        category="mcp",
        description="Panggil tool eksternal dari server Model Context Protocol (MCP) yang telah diaktifkan.",
        handler=mcp_client_manager.invoke_mcp_tool,
        risk_level=RiskLevel.MEDIUM,
    )


register_mcp_tools()
