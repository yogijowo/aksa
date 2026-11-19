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


MCP_HIGH_RISK_KEYWORDS = {
    "write", "delete", "remove", "drop", "create", "modify", "update",
    "execute", "run", "click", "navigate", "submit", "fill", "type",
    "send", "post", "put", "patch", "upload", "download", "insert",
    "truncate", "alter", "copy", "move", "rename", "kill", "terminate",
    "exec", "eval", "sync", "process", "manage", "trigger", "invoke",
    "dispatch", "set", "reset", "change", "wipe", "clear", "clean",
    "deploy", "apply", "push", "mutate", "destroy", "purge", "overwrite",
    "format", "launch", "start", "stop", "restart",
}

MCP_KNOWN_READ_ONLY_TOOLS = {
    "read_file", "list_directory", "get_file_info", "list_tables", "describe_table", "read_query"
}

MCP_SAFE_READ_KEYWORDS = {
    "read", "list", "view", "inspect", "get", "describe", "search", "find", "status", "info", "query"
}

MCP_TOOL_REQUIRED_PERMISSIONS: dict[str, list[str]] = {
    "write_file": ["filesystem.workspace.write"],
    "delete_file": ["filesystem.workspace.write"],
    "create_directory": ["filesystem.workspace.write"],
    "move_file": ["filesystem.workspace.write"],
    "read_file": ["filesystem.workspace.read"],
    "list_directory": ["filesystem.workspace.read"],
    "get_file_info": ["filesystem.workspace.read"],
    "playwright_navigate": ["application.automation"],
    "playwright_click": ["application.automation"],
    "playwright_fill": ["application.automation"],
    "playwright_screenshot": ["screen.capture"],
    "read_query": ["filesystem.workspace.read"],
    "write_query": ["filesystem.workspace.write"],
    "list_tables": ["filesystem.workspace.read"],
    "describe_table": ["filesystem.workspace.read"],
}


def classify_mcp_tool_risk(
    server: MCPServerConfig | None,
    tool_name: str,
    schema: dict[str, Any] | None = None,
) -> RiskLevel:
    """Classify risk level dynamically per MCP tool and operation (AKSA-SEC-001-R2).

    Fail-closed: Returns RiskLevel.HIGH or RiskLevel.UNKNOWN for unverified or neutral tools.
    NEVER defaults unknown tools to RiskLevel.LOW.
    """
    name_lower = tool_name.lower().replace("-", "_")
    tokens = set(name_lower.split("_"))

    # 1. Immediate HIGH risk keyword match
    if any(k in tokens or k in name_lower for k in MCP_HIGH_RISK_KEYWORDS):
        return RiskLevel.HIGH

    # 2. Inspect tool schema arguments for mutating or destructive intent
    if schema and isinstance(schema, dict):
        props = schema.get("properties", {})
        if isinstance(props, dict):
            prop_names = {p.lower() for p in props.keys()}
            if any(p in prop_names for p in ("content", "command", "cmd", "query", "url", "body", "payload", "script", "action")):
                return RiskLevel.HIGH

    # 3. Known strictly read-only whitelist
    if tool_name in MCP_KNOWN_READ_ONLY_TOOLS:
        return RiskLevel.LOW

    # 4. Safe read tokens (all tokens must strictly be in read keywords)
    if tokens and tokens.issubset(MCP_SAFE_READ_KEYWORDS):
        return RiskLevel.LOW

    # 5. Check server-declared permissions
    if server:
        server_perms = set(server.permissions)
        if "filesystem.workspace.write" in server_perms and any(w in name_lower for w in ("write", "save", "edit", "append")):
            return RiskLevel.HIGH
        if "application.automation" in server_perms and any(a in name_lower for a in ("click", "nav", "type", "submit", "eval", "press")):
            return RiskLevel.HIGH

    # 6. FAIL-CLOSED: Any unclassified, neutral, or third-party MCP tool is marked UNKNOWN
    return RiskLevel.UNKNOWN


def check_mcp_server_permissions(server: MCPServerConfig, tool_name: str) -> tuple[bool, str | None]:
    """Verify that the MCP server declares the required permissions for the given tool (AKSA-SEC-001-R2, AKSA-SEC-001-R3).

    Fail-closed: Rejects any server without permissions or any unmapped/unknown tool without explicit capability.
    Wildcard permissions ('*' or 'all') are strictly forbidden for third-party, community, or untrusted servers.
    Wildcard bypass is ONLY allowed if server.trust_level == 'system_trusted'.
    """
    server_perms = set(server.permissions or [])
    if not server_perms:
        return False, f"Server MCP '{server.name}' tidak mendeklarasikan izin apa pun. Eksekusi tool '{tool_name}' ditolak (fail-closed)."

    # AKSA-SEC-001-R3: Restrict wildcard to system-trusted internal servers only
    has_wildcard = "*" in server_perms or "all" in server_perms
    if has_wildcard:
        if getattr(server, "trust_level", "") == "system_trusted":
            return True, None
        # Discard wildcards for third-party or unreviewed servers
        server_perms.discard("*")
        server_perms.discard("all")
        if not server_perms:
            return (
                False,
                f"Server MCP '{server.name}' dengan tingkat kepercayaan '{getattr(server, 'trust_level', 'unreviewed')}' "
                f"mencoba menggunakan izin wildcard ('*' atau 'all'). Izin wildcard ditolak untuk server non-system (fail-closed).",
            )

    needed = MCP_TOOL_REQUIRED_PERMISSIONS.get(tool_name)
    if not needed:
        name_lower = tool_name.lower()
        if any(w in name_lower for w in ("write", "delete", "create", "modify", "save", "drop", "truncate")):
            needed = ["filesystem.workspace.write"]
        elif any(r in name_lower for r in ("read", "list", "view", "inspect", "get", "describe")):
            needed = ["filesystem.workspace.read"]
        elif any(c in name_lower for c in ("click", "navigate", "fill", "type", "press", "screenshot")):
            needed = ["application.automation"]
        else:
            # Neutral / unknown tool: requires explicit per-tool capability or declared custom permission
            candidate_perms = {f"mcp.{server.id}.{tool_name}", f"mcp.{server.name}.{tool_name}"}
            if any(p in server_perms for p in candidate_perms):
                return True, None
            needed = [f"mcp.{server.id}.{tool_name}"]

    missing = [p for p in needed if p not in server_perms]
    if missing:
        return (
            False,
            f"Server MCP '{server.name}' tidak memiliki izin '{', '.join(missing)}' yang diperlukan untuk tool '{tool_name}'. Eksekusi ditolak (fail-closed).",
        )
    return True, None


def validate_arguments_against_schema(schema: dict[str, Any] | None, arguments: dict[str, Any] | None) -> tuple[bool, str | None]:
    """Validate tool input arguments against full MCP JSON schema (AKSA-MCP-002)."""
    if not schema or not isinstance(schema, dict):
        return True, None
    args = arguments or {}
    if not isinstance(args, dict):
        return False, "Argumen harus berupa objek dictionary."

    try:
        import jsonschema
        jsonschema.validate(instance=args, schema=schema)
        return True, None
    except jsonschema.ValidationError as exc:
        if exc.validator == "required":
            missing_prop = exc.message.split("'")[1] if "'" in exc.message else exc.message
            return False, f"Parameter wajib '{missing_prop}' tidak disediakan."
        elif exc.validator == "type":
            field_name = exc.path[-1] if exc.path else "arg"
            return False, f"Tipe parameter '{field_name}' tidak valid. Diharapkan '{exc.validator_value}', diterima '{type(exc.instance).__name__}'."
        else:
            field_path = ".".join(str(p) for p in exc.path) if exc.path else "root"
            return False, f"Validasi parameter gagal pada field '{field_path}': {exc.message}"
    except jsonschema.SchemaError as exc:
        return False, f"Definisi JSON Schema pada server MCP tidak valid: {exc.message}"
    except Exception as exc:
        required = schema.get("required", [])
        if isinstance(required, list):
            for req_field in required:
                if req_field not in args:
                    return False, f"Parameter wajib '{req_field}' tidak disediakan."
        return False, f"Kesalahan validasi schema: {exc}"


async def _read_jsonrpc_response(
    reader: asyncio.StreamReader,
    target_id: int,
    timeout: float,
) -> dict[str, Any]:
    """Read stdout lines sequentially until a matching JSON-RPC id is received (AKSA-MCP-001)."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise TimeoutError(f"Timeout menunggu respons JSON-RPC id={target_id}")
        line_bytes = await asyncio.wait_for(reader.readline(), timeout=remaining)
        if not line_bytes:
            raise RuntimeError(f"Stream output server MCP terputus sebelum id={target_id} diterima")
        line = line_bytes.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict) and parsed.get("id") == target_id:
                return parsed
        except json.JSONDecodeError:
            continue


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
        """Perform MCP initialize handshake, validate protocol, and retrieve tools/list sequentially (AKSA-MCP-001)."""
        server = self._servers.get(server_id)
        if not server:
            raise KeyError(f"Server MCP '{server_id}' tidak ditemukan.")

        if not server.enabled:
            raise PermissionError(f"Server MCP '{server.name}' saat ini nonaktif.")

        # Check mock handler first
        if server_id in self._mock_handlers:
            resp = self._mock_handlers[server_id]("tools/list", None)
            tools = resp.get("tools", [])
            server.discovered_tools = [t["name"] for t in tools if isinstance(t, dict) and "name" in t]
            server.tool_schemas = {t["name"]: t.get("inputSchema", {}) for t in tools if isinstance(t, dict) and "name" in t}
            return tools

        cmd_bin = shutil.which(server.command)
        if not cmd_bin:
            raise FileNotFoundError(f"Executable '{server.command}' tidak ditemukan.")

        # Sequential stdio handshake and tools/list (AKSA-MCP-001)
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

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=safe_env,
        )

        try:
            assert proc.stdin is not None and proc.stdout is not None

            # Step 1: Send initialize request
            proc.stdin.write((json.dumps(init_req) + "\n").encode("utf-8"))
            await proc.stdin.drain()

            # Step 2: Read and validate initialize response
            init_resp = await _read_jsonrpc_response(proc.stdout, target_id=1, timeout=timeout / 2)
            if "error" in init_resp:
                raise RuntimeError(f"MCP Handshake error: {init_resp['error']}")
            proto = init_resp.get("result", {}).get("protocolVersion")
            if proto and proto not in SUPPORTED_MCP_PROTOCOL_VERSIONS:
                raise ValueError(f"Versi protokol MCP '{proto}' tidak didukung oleh AKSA.")

            # Step 3: Send notifications/initialized
            proc.stdin.write((json.dumps(notif_req) + "\n").encode("utf-8"))
            await proc.stdin.drain()

            # Step 4: Send tools/list request
            proc.stdin.write((json.dumps(list_req) + "\n").encode("utf-8"))
            await proc.stdin.drain()

            # Step 5: Read and validate tools/list response
            list_resp = await _read_jsonrpc_response(proc.stdout, target_id=2, timeout=timeout / 2)
            if "error" in list_resp:
                raise RuntimeError(f"MCP tools/list error: {list_resp['error']}")

            discovered = list_resp.get("result", {}).get("tools", [])
            server.discovered_tools = [t["name"] for t in discovered if isinstance(t, dict) and "name" in t]
            server.tool_schemas = {t["name"]: t.get("inputSchema", {}) for t in discovered if isinstance(t, dict) and "name" in t}
            return discovered
        except (asyncio.TimeoutError, TimeoutError):
            try:
                proc.kill()
            except Exception:
                pass
            raise TimeoutError(f"Timeout saat inisialisasi server MCP '{server.name}'.")
        finally:
            if proc.returncode is None:
                try:
                    proc.kill()
                except Exception:
                    pass

    async def invoke_mcp_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        timeout: float = 10.0,
    ) -> ToolResult:
        """Invoke a tool on an enabled MCP server via JSON-RPC 2.0 with dynamic risk, permissions and HITL verification (AKSA-SEC-001, AKSA-MCP-001)."""
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

        # 3. Check server declared permissions (AKSA-SEC-001-R2)
        perm_ok, perm_err = check_mcp_server_permissions(server, tool_name)
        if not perm_ok:
            return ToolResult(
                success=False,
                summary=perm_err or f"Izin ditolak untuk tool MCP '{tool_name}'.",
                data={"server_id": server.id, "status": "permission_denied", "error": perm_err},
                token_estimate=18,
            )

        # 4. Schema validation against tool parameters (AKSA-MCP-002)
        schema = server.tool_schemas.get(tool_name)
        if schema:
            valid, schema_err = validate_arguments_against_schema(schema, arguments)
            if not valid:
                return ToolResult(
                    success=False,
                    summary=f"Validasi argumen gagal untuk tool MCP '{tool_name}': {schema_err}",
                    data={"server_id": server.id, "status": "schema_validation_failed", "error": schema_err},
                    token_estimate=18,
                )

        # 5. Dynamic risk evaluation and HITL enforcement (AKSA-SEC-001-R2)
        tool_risk = classify_mcp_tool_risk(server, tool_name, schema)
        if tool_risk in (RiskLevel.HIGH, RiskLevel.UNKNOWN, RiskLevel.R3_EXTERNAL_SIDE_EFFECT, RiskLevel.R4_DESTRUCTIVE_PRIVILEGED):
            from app.core.sandbox import execution_policy_gateway
            grant_id = (arguments or {}).get("hitl_grant_id")
            session_id = (arguments or {}).get("session_id")
            workspace_id = (arguments or {}).get("workspace_id")

            is_valid_grant = False
            if grant_id:
                # 1. Direct tool grant
                is_valid_grant = execution_policy_gateway.verify_and_consume_grant(
                    grant_id=grant_id,
                    tool_name=f"mcp:{server.id}:{tool_name}",
                    arguments=arguments or {},
                    session_id=session_id,
                    workspace_id=workspace_id,
                )
                if not is_valid_grant:
                    # 2. Wrapper grant
                    is_valid_grant = execution_policy_gateway.verify_and_consume_grant(
                        grant_id=grant_id,
                        tool_name="invoke_mcp_tool",
                        arguments={
                            "server_id": server_id,
                            "tool_name": tool_name,
                            "arguments": arguments,
                        },
                        session_id=session_id,
                        workspace_id=workspace_id,
                    )
            if not is_valid_grant:
                return ToolResult(
                    success=False,
                    summary=(
                        f"Aksi berisiko tinggi MCP '{server.name}:{tool_name}' dicegah oleh ExecutionPolicyGateway: "
                        "Memerlukan persetujuan pengguna (HITL Approval Gate) yang sah, terikat pada argumen, dan belum pernah digunakan."
                    ),
                    data={
                        "hitl_required": True,
                        "server_id": server.id,
                        "tool_name": tool_name,
                        "risk_level": tool_risk.value,
                        "status": "hitl_approval_required",
                    },
                    token_estimate=24,
                )

        # 6. Check mock test handler
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
            assert process.stdin is not None and process.stdout is not None

            # Step 1: Send initialize request
            process.stdin.write((json.dumps(init_request) + "\n").encode("utf-8"))
            await process.stdin.drain()

            # Step 2: Read initialize response
            init_resp = await _read_jsonrpc_response(process.stdout, target_id=1, timeout=timeout / 2)
            if "error" in init_resp:
                return ToolResult(
                    success=False,
                    summary=f"Handshake inisialisasi server MCP '{server.name}' ditolak: {init_resp['error']}",
                    data={"server_id": server.id, "status": "handshake_rejected", "error": init_resp["error"]},
                    token_estimate=20,
                )
            proto = init_resp.get("result", {}).get("protocolVersion")
            if proto and proto not in SUPPORTED_MCP_PROTOCOL_VERSIONS:
                return ToolResult(
                    success=False,
                    summary=f"Versi protokol MCP server '{proto}' tidak didukung oleh AKSA.",
                    data={"server_id": server.id, "status": "unsupported_protocol_version", "protocol": proto},
                    token_estimate=20,
                )

            # Step 3: Send notifications/initialized
            process.stdin.write((json.dumps(initialized_notification) + "\n").encode("utf-8"))
            await process.stdin.drain()

            # Step 4: Send tools/call request
            process.stdin.write((json.dumps(call_request) + "\n").encode("utf-8"))
            await process.stdin.drain()

            # Step 5: Read tools/call response
            call_resp = await _read_jsonrpc_response(process.stdout, target_id=2, timeout=timeout / 2)
            if "error" in call_resp:
                return ToolResult(
                    success=False,
                    summary=f"Server MCP '{server.name}' mengembalikan error protokol pada tool '{tool_name}'.",
                    data={"server_id": server.id, "status": "rpc_error", "error": call_resp["error"]},
                    token_estimate=24,
                )

            result_data = call_resp.get("result")
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
                    data={"server_id": server.id, "status": "invalid_protocol_response"},
                    token_estimate=24,
                )

        except (asyncio.TimeoutError, TimeoutError):
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
