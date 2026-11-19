"""Dynamic Tool Registry, Structured ToolResult, and Category Loader."""

from __future__ import annotations

import inspect
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.sandbox import RiskLevel

# Deterministic, strictly workspace-scoped tools allowed inside SkillEvaluator runtime replay (P1-02).
# Never include external network/MCP, live computer-use GUI, OS COM/AppleScript, subprocess,
# or persistent production RAG/memory mutation tools.
REPLAY_ALLOWED_TOOLS: frozenset[str] = frozenset({
    "word_inspect",
    "word_create_document",
    "word_fill_template",
    "excel_inspect",
    "excel_create_workbook",
    "excel_modify_cells",
    "ppt_create_presentation",
    "pdf_extract_markdown",
    "pdf_generate_report",
    "pdf_merge_split",
    "list_workspace_files",
    "inspect_file_outline",
    "search_files",
    "move_or_copy_file",
})


class ToolResult(BaseModel):
    """Structured output returned by every AKSA tool execution."""

    success: bool
    summary: str
    data: Any = None
    artifacts: list[str] = Field(default_factory=list)
    token_estimate: int = 0


ToolHandler = Callable[..., Awaitable[ToolResult]]


class RegisteredTool(BaseModel):
    """Metadata and schema for a registered AKSA tool."""

    name: str
    category: str
    description: str
    risk_level: RiskLevel = RiskLevel.LOW
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    replay_safe: bool = False


class ToolRegistry:
    """Central registry mapping tool names and categories to async handlers."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(
        self,
        name: str,
        category: str,
        description: str,
        handler: ToolHandler,
        risk_level: RiskLevel = RiskLevel.LOW,
        parameters_schema: dict[str, Any] | None = None,
        replay_safe: bool | None = None,
    ) -> None:
        """Register an async tool handler under a specific category."""
        # Restrict replay_safe strictly to the explicit deterministic allowlist (fail-closed)
        is_replay_safe = (name in REPLAY_ALLOWED_TOOLS) if replay_safe is None else bool(replay_safe and name in REPLAY_ALLOWED_TOOLS)
        self._tools[name] = RegisteredTool(
            name=name,
            category=category,
            description=description,
            risk_level=risk_level,
            parameters_schema=parameters_schema or {"type": "object", "properties": {}},
            replay_safe=is_replay_safe,
        )
        self._handlers[name] = handler

    def list_tools(self, categories: list[str] | None = None) -> list[RegisteredTool]:
        """List registered tools optionally filtered by category."""
        items = list(self._tools.values())
        if categories is not None:
            cat_set = set(categories)
            items = [t for t in items if t.category in cat_set]
        return items

    def get_tool(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def get_schemas_for_categories(self, categories: list[str]) -> list[dict[str, Any]]:
        """Generate OpenAI/Gemini/Anthropic-compatible function schemas for tools matching the specified categories."""
        tools = self.list_tools(categories=categories)
        schemas: list[dict[str, Any]] = []
        for t in tools:
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters_schema if t.parameters_schema else {"type": "object", "properties": {}},
                    },
                }
            )
        return schemas

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        """Execute a registered tool by name through the centralized ExecutionPolicyGateway."""
        tool = self._tools.get(name)
        handler = self._handlers.get(name)
        if not tool or not handler:
            return ToolResult(
                success=False,
                summary=f"Tool '{name}' tidak terdaftar di dalam ToolRegistry AKSA.",
                token_estimate=12,
            )

        from app.core.sandbox import execution_policy_gateway

        effective_risk = tool.risk_level
        if name == "invoke_mcp_tool":
            from app.tools.mcp.mcp_client import classify_mcp_tool_risk, mcp_client_manager
            server_id = kwargs.get("server_id", "")
            tool_name = kwargs.get("tool_name", "")
            server = mcp_client_manager.get_server(server_id)
            schema = server.tool_schemas.get(tool_name) if server else None
            effective_risk = classify_mcp_tool_risk(server, tool_name, schema)

        session_id = kwargs.get("session_id")
        return await execution_policy_gateway.execute_tool(
            tool_name=name,
            handler=handler,
            risk_level=effective_risk,
            arguments=kwargs,
            session_id=session_id,
        )

    async def execute_replay(
        self,
        name: str,
        replay_workspace: Path,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a deterministic workspace-scoped tool cleanly for sandboxed skill replay.

        Enforces an explicit allowlist (``REPLAY_ALLOWED_TOOLS``), rejects policy/grant override
        fields, validates arguments against declared schemas/signatures, and verifies that the active
        ``SandboxManager`` jail is locked exclusively to ``replay_workspace`` with ``allow_execute=False``.
        """
        tool = self._tools.get(name)
        handler = self._handlers.get(name)
        if not tool or not handler:
            return ToolResult(
                success=False,
                summary=f"Tool '{name}' tidak ditemukan untuk runtime replay.",
                token_estimate=12,
            )

        if name not in REPLAY_ALLOWED_TOOLS or not tool.replay_safe:
            return ToolResult(
                success=False,
                summary=(
                    f"Replay ditolak (fail-closed): Tool '{name}' tidak termasuk daftar putih replay "
                    "deterministik karena dapat mengakses jaringan, OS, komputer live, atau state produksi."
                ),
                token_estimate=18,
            )

        from app.core.sandbox import FORBIDDEN_POLICY_OVERRIDE_FIELDS, sandbox_manager

        forbidden_keys = sorted(
            k for k in kwargs if k in FORBIDDEN_POLICY_OVERRIDE_FIELDS or k == "hitl_grant_id"
        )
        if forbidden_keys:
            return ToolResult(
                success=False,
                summary=f"Replay ditolak: Parameter override kebijakan terlarang ({', '.join(forbidden_keys)}).",
                token_estimate=16,
            )

        # Validate arguments against declared parameters_schema or Python handler signature
        schema = tool.parameters_schema or {}
        props = schema.get("properties") if isinstance(schema, dict) else None
        req_fields = schema.get("required") if isinstance(schema, dict) else None
        if isinstance(req_fields, list):
            missing = [f for f in req_fields if f not in kwargs]
            if missing:
                return ToolResult(
                    success=False,
                    summary=f"Replay ditolak: Argumen wajib tidak lengkap untuk '{name}': {missing}.",
                    token_estimate=16,
                )
        if isinstance(props, dict) and props:
            unknown_keys = [k for k in kwargs if k not in props]
            if unknown_keys:
                return ToolResult(
                    success=False,
                    summary=f"Replay ditolak: Argumen tidak sesuai skema pada '{name}': {unknown_keys}.",
                    token_estimate=16,
                )
        else:
            sig = inspect.signature(handler)
            has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
            if not has_varkw:
                unknown_keys = [k for k in kwargs if k not in sig.parameters]
                if unknown_keys:
                    return ToolResult(
                        success=False,
                        summary=f"Replay ditolak: Parameter tidak dikenal pada '{name}': {unknown_keys}.",
                        token_estimate=16,
                    )

        # Enforce SandboxManager is strictly jailed to replay_workspace ONLY (allow_execute=False)
        ws_real = Path(os.path.realpath(str(replay_workspace)))
        policies = sandbox_manager.list_policies()
        if len(policies) != 1:
            return ToolResult(
                success=False,
                summary="Replay ditolak: SandboxManager harus terkunci eksklusif pada satu workspace replay terisolasi.",
                token_estimate=16,
            )
        active_ws = Path(os.path.realpath(policies[0].folder_path))
        if active_ws != ws_real or policies[0].allow_execute or not policies[0].allow_read:
            return ToolResult(
                success=False,
                summary="Replay ditolak: Kebijakan SandboxManager tidak terisolasi ke workspace replay.",
                token_estimate=16,
            )

        return await handler(**kwargs)


tool_registry = ToolRegistry()

