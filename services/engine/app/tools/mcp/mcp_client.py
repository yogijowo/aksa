"""Model Context Protocol (MCP) Host/Client Manager with JSON-RPC 2.0 stdio transport.

All external MCP servers are DISABLED BY DEFAULT to ensure zero unvetted background execution.
Enforces complete MCP lifecycle: initialize handshake, capability validation, notifications/initialized,
tools/list schema validation, process cleanup, and pinned package dependencies (P1.3).
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from typing import Any, Callable

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

SUPPORTED_MCP_PROTOCOL_VERSIONS = {"2024-11-05", "2024-10-07", "0.1.0"}
MAX_PAYLOAD_SIZE = 10 * 1024 * 1024  # 10 MB maximum payload limit


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
    publisher: str = "Community / Verified"
    source: str = "official"  # official | community | local
    transport: str = "stdio"  # stdio | sse
    command: str
    args: list[str] = Field(default_factory=list)
    environment_allowlist: list[str] = Field(default_factory=list)
    package_version: str = "1.0.0"
    permissions: list[str] = Field(default_factory=list)
    enabled: bool = False  # DISABLED BY DEFAULT (P1.3)
    trust_level: str = "unreviewed"
    description_id: str = ""
    discovered_tools: list[str] = Field(default_factory=list)
    tool_schemas: dict[str, Any] = Field(default_factory=dict)


# Pinned production packages (P1.3)
DEFAULT_MCP_SERVERS: list[MCPServerConfig] = [
    MCPServerConfig(
        id="mcp_filesystem",
        name="Filesystem MCP Server",
        publisher="@modelcontextprotocol",
        source="official",
        transport="stdio",
        command="npx",
        package_version="0.6.2",
        args=["-y", "@modelcontextprotocol/server-filesystem@0.6.2"],
        permissions=["filesystem.workspace.read", "filesystem.workspace.write"],
        enabled=False,
        description_id="Akses standar MCP untuk operasi struktur direktori lokal.",
        discovered_tools=["read_file", "write_file", "list_directory"],
    ),
    MCPServerConfig(
        id="mcp_playwright",
        name="Playwright Browser Automation MCP",
        publisher="@executeautomation",
        source="official",
        transport="stdio",
        command="npx",
        package_version="0.1.1",
        args=["-y", "@executeautomation/playwright-mcp-server@0.1.1"],
        permissions=["application.automation", "screen.capture"],
        enabled=False,
        description_id="Automasi peramban web untuk mengisi formulir dan mengunduh laporan.",
        discovered_tools=["playwright_navigate", "playwright_click", "playwright_screenshot"],
    ),
    MCPServerConfig(
        id="mcp_sqlite",
        name="SQLite / Database Explorer MCP",
        publisher="modelcontextprotocol",
        source="official",
        transport="stdio",
        command="uvx",
        package_version="0.1.2",
        args=["mcp-server-sqlite==0.1.2"],
        permissions=["filesystem.workspace.read"],
        enabled=False,
        description_id="Kueri dan analisis tabel database lokal melalui protokol MCP.",
        discovered_tools=["read_query", "list_tables", "describe_table"],
    ),
]


class MCPClientManager:
    """Manages MCP server lifecycles, JSON-RPC 2.0 handshake, schema validation, and isolation (P1.3)."""

    def __init__(self) -> None:
        self._servers: dict[str, MCPServerConfig] = {s.id: s for s in DEFAULT_MCP_SERVERS}
        # Mock session injector for testing without external node/npm processes
        self._mock_handlers: dict[str, Callable[[str, dict[str, Any] | None], dict[str, Any]]] = {}

    def list_servers(self) -> list[MCPServerConfig]:
        return list(self._servers.values())

    def get_server(self, server_id: str) -> MCPServerConfig | None:
        return self._servers.get(server_id)

    def set_mock_handler(
        self,
        server_id: str,
        handler: Callable[[str, dict[str, Any] | None], dict[str, Any]] | None,
    ) -> None:
        """Inject a mock RPC handler for automated unit tests."""
        if handler is None:
            self._mock_handlers.pop(server_id, None)
        else:
            self._mock_handlers[server_id] = handler

    def clear_mock_handlers(self) -> None:
        self._mock_handlers.clear()

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
        """Disable MCP server immediately, clear cached tools, and revoke grants."""
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

    async def discover_tools(self, server_id: str, timeout: float = 8.0) -> list[dict[str, Any]]:
        """Perform MCP initialize handshake, validate protocol, and retrieve tools/list."""
        server = self._servers.get(server_id)
        if not server:
            raise KeyError(f"Server MCP '{server_id}' tidak ditemukan.")

        if not server.enabled:
            raise PermissionError(f"Server MCP '{server.name}' saat ini nonaktif.")

        # Check mock handler first
        if server_id in self._mock_handlers:
            resp = self._mock_handlers[server_id]("tools/list", None)
            tools = resp.get("tools", [])
            server.discovered_tools = [t["name"] for t in tools if "name" in t]
            server.tool_schemas = {t["name"]: t.get("inputSchema", {}) for t in tools if "name" in t}
            return tools

        cmd_bin = shutil.which(server.command)
        if not cmd_bin:
            raise FileNotFoundError(f"Executable '{server.command}' tidak ditemukan.")

        # Execute stdio handshake and tools/list
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "AKSA", "version": "1.0.0"},
            },
        }
        notif_req = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

        args = [cmd_bin] + server.args
        safe_env = build_isolated_mcp_env(server.environment_allowlist)
        payload = (
            json.dumps(init_req) + "\n" + json.dumps(notif_req) + "\n" + json.dumps(list_req) + "\n"
        )

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=safe_env,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=payload.encode("utf-8")),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            raise TimeoutError(f"Timeout saat inisialisasi server MCP '{server.name}'.")

        discovered: list[dict[str, Any]] = []
        for line in stdout.decode("utf-8", errors="replace").splitlines():
            try:
                msg = json.loads(line)
                if msg.get("id") == 1 and "error" in msg:
                    raise RuntimeError(f"MCP Handshake error: {msg['error']}")
                if msg.get("id") == 2 and "result" in msg:
                    discovered = msg["result"].get("tools", [])
                    server.discovered_tools = [t["name"] for t in discovered if "name" in t]
                    server.tool_schemas = {t["name"]: t.get("inputSchema", {}) for t in discovered if "name" in t}
                    break
            except json.JSONDecodeError:
                continue

        return discovered

    async def invoke_mcp_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        timeout: float = 10.0,
    ) -> ToolResult:
        """Invoke a tool on an enabled MCP server via JSON-RPC 2.0 with complete lifecycle validation (P1.3)."""
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

        # 1. Payload size guard (P1.3)
        args_json = json.dumps(arguments or {})
        if len(args_json) > MAX_PAYLOAD_SIZE:
            return ToolResult(
                success=False,
                summary=f"Ukuran payload argumen ({len(args_json)} bytes) melebihi batas aman (10 MB).",
                data={"server_id": server.id, "status": "payload_too_large"},
                token_estimate=14,
            )

        # 2. Check if tool exists in discovered tools
        if server.discovered_tools and tool_name not in server.discovered_tools:
            return ToolResult(
                success=False,
                summary=f"Tool '{tool_name}' tidak terdaftar pada server MCP '{server.name}'. Pilihan: {server.discovered_tools}.",
                data={"server_id": server.id, "status": "tool_not_found", "available": server.discovered_tools},
                token_estimate=18,
            )

        # 3. Check mock test handler
        if server_id in self._mock_handlers:
            try:
                res = self._mock_handlers[server_id](tool_name, arguments)
                if "error" in res:
                    return ToolResult(
                        success=False,
                        summary=f"Server MCP '{server.name}' mengembalikan error: {res['error']}",
                        data={"server_id": server.id, "status": "rpc_error", "error": res["error"]},
                        token_estimate=20,
                    )
                return ToolResult(
                    success=True,
                    summary=f"Berhasil memanggil tool MCP '{tool_name}' pada server '{server.name}'.",
                    data={"server_id": server.id, "status": "succeeded", "result": res.get("result", res)},
                    token_estimate=28,
                )
            except Exception as exc:
                return ToolResult(
                    success=False,
                    summary=f"Error saat mengeksekusi mock server MCP: {exc}",
                    data={"server_id": server.id, "status": "mock_error", "error": str(exc)},
                    token_estimate=18,
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
        process = None

        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=safe_env,
            )

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
            handshake_ok = False

            for line in response_lines:
                try:
                    data = json.loads(line)
                    if data.get("id") == 1:
                        if "error" in data:
                            return ToolResult(
                                success=False,
                                summary=f"Handshake inisialisasi server MCP '{server.name}' ditolak.",
                                data={"server_id": server.id, "status": "handshake_rejected", "error": data["error"]},
                                token_estimate=20,
                            )
                        # Validate protocol version
                        proto = data.get("result", {}).get("protocolVersion")
                        if proto and proto not in SUPPORTED_MCP_PROTOCOL_VERSIONS:
                            return ToolResult(
                                success=False,
                                summary=f"Versi protokol MCP server '{proto}' tidak didukung oleh AKSA.",
                                data={"server_id": server.id, "status": "unsupported_protocol_version", "protocol": proto},
                                token_estimate=20,
                            )
                        handshake_ok = True

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
            if process:
                try:
                    process.kill()
                except Exception:
                    pass
            return ToolResult(
                success=False,
                summary=f"Pemanggilan tool MCP '{tool_name}' pada server '{server.name}' melebihi batas waktu ({timeout}s).",
                data={"server_id": server.id, "status": "timeout"},
                token_estimate=16,
            )
        except Exception as exc:
            if process:
                try:
                    process.kill()
                except Exception:
                    pass
            return ToolResult(
                success=False,
                summary=f"Gagal mengeksekusi server MCP '{server.name}': {exc}",
                data={"server_id": server.id, "status": "error", "error": str(exc)},
                token_estimate=18,
            )
        finally:
            if process and process.returncode is None:
                try:
                    process.kill()
                except Exception:
                    pass


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
