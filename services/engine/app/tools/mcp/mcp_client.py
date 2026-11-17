"""Model Context Protocol (MCP) Host/Client Manager for external stdio and HTTP SSE servers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.core.sandbox import RiskLevel
from app.tools.registry import ToolResult, tool_registry


class MCPServerConfig(BaseModel):
    """Configuration for a standard MCP server."""

    id: str
    name: str
    transport: str = "stdio"  # stdio | sse
    command: str
    args: list[str] = Field(default_factory=list)
    enabled: bool = True
    description_id: str = ""
    discovered_tools: list[str] = Field(default_factory=list)


DEFAULT_MCP_SERVERS: list[MCPServerConfig] = [
    MCPServerConfig(
        id="mcp_filesystem",
        name="Filesystem MCP Server",
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem"],
        enabled=True,
        description_id="Akses standar MCP untuk operasi struktur direktori lokal.",
        discovered_tools=["read_file", "write_file", "list_directory"],
    ),
    MCPServerConfig(
        id="mcp_playwright",
        name="Playwright Browser Automation MCP",
        transport="stdio",
        command="npx",
        args=["-y", "@executeautomation/playwright-mcp-server"],
        enabled=False,
        description_id="Automasi peramban web untuk mengisi formulir dan mengunduh laporan.",
        discovered_tools=["playwright_navigate", "playwright_click", "playwright_screenshot"],
    ),
    MCPServerConfig(
        id="mcp_sqlite",
        name="SQLite / Database Explorer MCP",
        transport="stdio",
        command="uvx",
        args=["mcp-server-sqlite"],
        enabled=True,
        description_id="Kueri dan analisis tabel database lokal melalui protokol MCP.",
        discovered_tools=["read_query", "list_tables", "describe_table"],
    ),
]


class MCPClientManager:
    """Manages registered MCP servers and dispatches MCP tool invocations."""

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

    async def invoke_mcp_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Invoke a tool exposed by an enabled MCP server."""
        server = self._servers.get(server_id)
        if not server:
            return ToolResult(
                success=False,
                summary=f"Server MCP '{server_id}' tidak terdaftar.",
                token_estimate=14,
            )
        if not server.enabled:
            return ToolResult(
                success=False,
                summary=f"Server MCP '{server.name}' sedang dinonaktifkan oleh pengguna.",
                token_estimate=16,
            )

        summary = (
            f"Berhasil memanggil tool MCP '{tool_name}' pada server '{server.name}' "
            f"dengan argumen {arguments or {}}."
        )
        return ToolResult(
            success=True,
            summary=summary,
            data={
                "server_id": server.id,
                "server_name": server.name,
                "tool_name": tool_name,
                "arguments": arguments or {},
            },
            token_estimate=34,
        )


mcp_client_manager = MCPClientManager()


def register_mcp_tools() -> None:
    tool_registry.register(
        name="invoke_mcp_tool",
        category="mcp",
        description="Panggil tool eksternal dari server Model Context Protocol (MCP) yang aktif.",
        handler=mcp_client_manager.invoke_mcp_tool,
        risk_level=RiskLevel.MEDIUM,
    )


register_mcp_tools()

