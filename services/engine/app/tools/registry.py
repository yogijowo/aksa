"""Dynamic Tool Registry, Structured ToolResult, and Category Loader."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, Field

from app.core.sandbox import RiskLevel


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
    ) -> None:
        """Register an async tool handler under a specific category."""
        self._tools[name] = RegisteredTool(
            name=name,
            category=category,
            description=description,
            risk_level=risk_level,
            parameters_schema=parameters_schema or {"type": "object", "properties": {}},
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


tool_registry = ToolRegistry()

