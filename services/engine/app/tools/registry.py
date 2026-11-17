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

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        """Execute a registered tool by name and return a structured ToolResult."""
        handler = self._handlers.get(name)
        if not handler:
            return ToolResult(
                success=False,
                summary=f"Tool '{name}' tidak terdaftar di dalam ToolRegistry AKSA.",
                token_estimate=12,
            )
        return await handler(**kwargs)


tool_registry = ToolRegistry()

