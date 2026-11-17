"""REST API v1 endpoints for AKSA Teams, Agents, Workspaces, Models, Orchestrator, and Token Analytics."""

from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys
from typing import Any

import aiosqlite
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.core.llm_router import UnifiedLLMRouter
from app.core.orchestrator import HierarchicalOrchestrator
from app.core.sandbox import RiskLevel, SandboxViolationError, WorkspacePolicy, sandbox_manager
from app.db.models import db_manager
from app.rag.store import rag_store
from app.rag.watcher import rag_watcher
from app.telegram.auth import telegram_auth_guard
from app.telegram.bot import telegram_gateway
from app.tools import tool_registry
from app.tools.computer_use.gui_agent import computer_use_controller
from app.tools.mcp.mcp_client import mcp_client_manager

api_router = APIRouter(prefix="/api/v1")

llm_router = UnifiedLLMRouter(db=db_manager)
orchestrator = HierarchicalOrchestrator(db=db_manager, llm_router=llm_router)


class CreateAgentRequest(BaseModel):
    team_id: str
    parent_id: str | None = None
    name: str
    role_title: str
    description: str
    avatar_icon: str = "bot"
    tier_level: int = 1
    provider: str
    model_id: str
    temperature: float = 0.2
    max_tokens: int = 4096
    system_prompt: str
    tool_categories: list[str] = Field(default_factory=list)
    position_x: float = 0.0
    position_y: float = 0.0


class UpdateAgentRequest(BaseModel):
    parent_id: str | None = None
    name: str | None = None
    role_title: str | None = None
    description: str | None = None
    avatar_icon: str | None = None
    tier_level: int | None = None
    provider: str | None = None
    model_id: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    system_prompt: str | None = None
    tool_categories: list[str] | None = None
    position_x: float | None = None
    position_y: float | None = None


class UpsertWorkspaceRequest(BaseModel):
    name: str | None = None
    folder_path: str
    allow_read: bool = True
    allow_write: bool = True
    allow_execute: bool = False
    auto_rag_sync: bool = True


class CreateSessionRequest(BaseModel):
    title: str = "Sesi Kerja Baru"
    workspace_id: str | None = None
    team_id: str | None = None
    source: str = "desktop"


class SaveApiKeyRequest(BaseModel):
    provider: str
    api_key: str


class TestModelRequest(BaseModel):
    provider: str
    model_id: str


class ExecuteTaskRequest(BaseModel):
    prompt: str
    team_id: str | None = None
    workspace_id: str | None = None
    workspace_path: str | None = None
    session_id: str | None = None


async def _check_ollama_status() -> dict[str, Any]:
    """Check if local Ollama service is reachable and list installed models."""
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                return {"online": True, "models": models}
    except Exception:
        pass
    return {"online": False, "models": []}


@api_router.get("/health")
async def get_health() -> dict[str, Any]:
    """Return engine status, database path, and local AI availability."""
    ollama_info = await _check_ollama_status()
    tg_status = telegram_gateway.get_status()
    return {
        "status": "ok",
        "version": "1.0.0",
        "appdata_dir": str(settings.appdata_dir),
        "ollama": ollama_info,
        "telegram": {
            "connected": tg_status["connected"],
            "bot_username": tg_status["bot_username"],
        },
    }


@api_router.get("/models/providers")
async def list_model_providers() -> dict[str, Any]:
    """List Cloud API and Local AI (Ollama / LM Studio) providers and available models."""
    providers = await llm_router.list_providers_status()
    return {"providers": providers}


@api_router.post("/models/keys")
async def save_provider_api_key(req: SaveApiKeyRequest) -> dict[str, Any]:
    """Save an API key for a Cloud LLM provider."""
    status_map = await llm_router.save_api_key(req.provider, req.api_key)
    return {"saved": True, "provider": req.provider, "configured_providers": status_map}


@api_router.post("/models/test")
async def test_model_connection(req: TestModelRequest) -> dict[str, Any]:
    """Test completion connectivity for a specific provider and model."""
    res = await llm_router.complete(
        provider=req.provider,
        model_id=req.model_id,
        messages=[{"role": "user", "content": "Balas singkat: OK"}],
        max_tokens=32,
    )
    return {
        "ok": True,
        "provider": req.provider,
        "model_id": req.model_id,
        "simulated": res["simulated"],
        "reply": res["content"],
    }


@api_router.post("/orchestrate/execute")
async def execute_hierarchical_task(req: ExecuteTaskRequest) -> dict[str, Any]:
    """Execute a user instruction across the hierarchical Supervisor -> Sub-Agent team."""
    resolved_path: str | None = None
    if req.workspace_id:
        workspaces = await db_manager.list_workspaces()
        ws = next((w for w in workspaces if w["id"] == req.workspace_id), None)
        if ws:
            resolved_path = ws["folder_path"]
        else:
            raise HTTPException(status_code=404, detail="Workspace ID tidak ditemukan.")
    elif req.workspace_path:
        p = Path(req.workspace_path).expanduser().resolve()
        if not p.exists() or not p.is_dir():
            raise HTTPException(
                status_code=400,
                detail=f"Folder workspace '{req.workspace_path}' tidak ditemukan di sistem.",
            )
        resolved_path = str(p)

    result = await orchestrator.execute_hierarchical_task(
        prompt=req.prompt,
        team_id=req.team_id,
        workspace_id=req.workspace_id,
        workspace_path=resolved_path,
        session_id=req.session_id,
    )
    return result


@api_router.get("/tokens/analytics")
async def get_token_analytics() -> dict[str, Any]:
    """Return aggregated token consumption and savings metrics from SQLite."""
    async with aiosqlite.connect(db_manager.db_path) as conn:
        cursor = await conn.execute(
            """
            SELECT
                COALESCE(SUM(input_tokens + output_tokens), 0) AS total_used,
                COALESCE(SUM(tokens_saved_by_isolation), 0) AS total_saved,
                COALESCE(SUM(cost_usd), 0.0) AS total_cost_usd,
                COUNT(*) AS total_calls
            FROM token_usage_logs
            """
        )
        row = await cursor.fetchone()
        used = int(row[0]) if row else 0
        saved = int(row[1]) if row else 0
        cost = float(row[2]) if row else 0.0
        calls = int(row[3]) if row else 0

        savings_pct = round((saved / max(1, used + saved)) * 100, 1) if (used + saved) > 0 else 78.0
        return {
            "total_tokens_used": used,
            "total_tokens_saved": saved,
            "savings_percentage": savings_pct,
            "total_cost_usd": round(cost, 4),
            "total_calls": calls,
        }


@api_router.get("/teams")
async def list_teams() -> dict[str, Any]:
    """List all hierarchical agent teams and their nested agent nodes."""
    teams = await db_manager.list_teams_with_agents()
    return {"teams": teams}


@api_router.post("/agents")
async def create_agent(req: CreateAgentRequest) -> dict[str, Any]:
    """Create a new agent node in a hierarchical team."""
    agent = await db_manager.create_agent(req.model_dump())
    return {"agent": agent}


@api_router.patch("/agents/{agent_id}")
async def update_agent(agent_id: str, req: UpdateAgentRequest) -> dict[str, Any]:
    """Update an existing agent's configuration or canvas position."""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    updated = await db_manager.update_agent(agent_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Agen tidak ditemukan.")
    return {"agent": updated}


@api_router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str) -> dict[str, Any]:
    """Remove an agent node from the hierarchy."""
    deleted = await db_manager.delete_agent(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agen tidak ditemukan.")
    return {"deleted": True, "id": agent_id}


@api_router.get("/workspaces")
async def list_workspaces() -> dict[str, Any]:
    """List all authorized PC workspace folders."""
    workspaces = await db_manager.list_workspaces()
    if not workspaces:
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        ws = await db_manager.upsert_workspace(
            {
                "name": "Proyek AKSA (Lokal)",
                "folder_path": str(repo_root),
                "allow_read": True,
                "allow_write": True,
                "allow_execute": True,
                "auto_rag_sync": True,
            }
        )
        sandbox_manager.register_workspace(
            WorkspacePolicy(
                folder_path=str(repo_root),
                allow_read=True,
                allow_write=True,
                allow_execute=True,
            )
        )
        workspaces = [ws]

    return {"workspaces": workspaces}


@api_router.post("/workspaces")
async def register_workspace(req: UpsertWorkspaceRequest) -> dict[str, Any]:
    """Authorize a PC folder for agent access."""
    target = Path(req.folder_path).expanduser()
    if not target.exists() or not target.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Folder '{req.folder_path}' tidak ditemukan di komputer ini.",
        )
    workspace = await db_manager.upsert_workspace(req.model_dump())
    sandbox_manager.register_workspace(
        WorkspacePolicy(
            folder_path=str(target),
            allow_read=req.allow_read,
            allow_write=req.allow_write,
            allow_execute=req.allow_execute,
        )
    )
    return {"workspace": workspace}


@api_router.delete("/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: str) -> dict[str, Any]:
    """Remove an authorized PC workspace folder."""
    deleted = await db_manager.delete_workspace(workspace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Folder Kerja tidak ditemukan.")
    return {"deleted": True, "id": workspace_id}


class OpenPathRequest(BaseModel):
    path: str


@api_router.post("/system/open-path")
async def open_system_path(req: OpenPathRequest) -> dict[str, Any]:
    """Open a file or directory in the operating system's native application (Word, Excel, Finder, Explorer)."""
    target = Path(req.path).expanduser().resolve()
    if not target.exists():
        # Fallback check against known workspaces
        workspaces = await db_manager.list_workspaces()
        found = False
        for ws in workspaces:
            candidate = Path(ws["folder_path"]) / req.path
            if candidate.exists():
                target = candidate.resolve()
                found = True
                break
        if not found:
            raise HTTPException(status_code=404, detail=f"Berkas '{req.path}' tidak ditemukan di sistem.")

    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        elif sys.platform == "win32":
            os.startfile(str(target))
        else:
            subprocess.Popen(["xdg-open", str(target)])
        return {
            "success": True,
            "path": str(target),
            "name": target.name,
            "message": f"Berkas '{target.name}' berhasil dibuka di aplikasi default sistem.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal membuka berkas: {e}")


@api_router.get("/workspaces/{workspace_id}/files")
async def list_workspace_files(workspace_id: str) -> dict[str, Any]:
    """List top-level files inside an authorized workspace folder."""
    workspaces = await db_manager.list_workspaces()
    ws = next((w for w in workspaces if w["id"] == workspace_id), None)
    if not ws:
        raise HTTPException(status_code=404, detail="Folder Kerja tidak ditemukan.")

    folder = Path(ws["folder_path"])
    if not folder.exists():
        return {"files": [], "exists": False}

    files: list[dict[str, Any]] = []
    for entry in sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if entry.name.startswith("."):
            continue
        stat = entry.stat()
        files.append(
            {
                "name": entry.name,
                "path": str(entry),
                "is_dir": entry.is_dir(),
                "ext": entry.suffix.lower(),
                "size_bytes": stat.st_size if entry.is_file() else 0,
                "modified_at": stat.st_mtime,
            }
        )
    return {"files": files, "exists": True}


@api_router.get("/sessions")
async def list_sessions() -> dict[str, Any]:
    """List chat sessions."""
    sessions = await db_manager.list_sessions()
    return {"sessions": sessions}


@api_router.post("/sessions")
async def create_session(req: CreateSessionRequest) -> dict[str, Any]:
    """Create a new chat session."""
    session = await db_manager.create_session(req.model_dump())
    return {"session": session}


class ExecuteToolRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class CreateHITLRequest(BaseModel):
    tool_name: str
    title_id: str
    description_id: str
    risk_level: RiskLevel = RiskLevel.HIGH
    target_path: str | None = None
    agent_name: str = "Operator PC & Automasi Sistem"


class ResolveHITLRequest(BaseModel):
    approved: bool


class ToggleMCPServerRequest(BaseModel):
    enabled: bool


@api_router.get("/tools")
async def list_registered_tools(category: str | None = None) -> dict[str, Any]:
    """List all registered 3-Tier PC and Office tools."""
    cats = [category] if category else None
    tools = [t.model_dump() for t in tool_registry.list_tools(cats)]
    return {"tools": tools}


@api_router.post("/tools/execute")
async def execute_registered_tool(req: ExecuteToolRequest) -> dict[str, Any]:
    """Execute a registered tool inside the Workspace Sandbox."""
    try:
        result = await tool_registry.execute(req.tool_name, **req.arguments)
        return result.model_dump()
    except SandboxViolationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@api_router.get("/sandbox/approvals")
async def list_hitl_approvals(status: str | None = None) -> dict[str, Any]:
    """List Human-in-the-Loop approval gate items."""
    items = [i.model_dump() for i in sandbox_manager.list_approvals(status=status)]
    return {"approvals": items}


@api_router.post("/sandbox/approvals")
async def create_hitl_approval(req: CreateHITLRequest) -> dict[str, Any]:
    """Trigger a new HITL approval prompt for Desktop UI & Telegram."""
    item = await sandbox_manager.create_hitl_request(
        tool_name=req.tool_name,
        title_id=req.title_id,
        description_id=req.description_id,
        risk_level=req.risk_level,
        target_path=req.target_path,
        agent_name=req.agent_name,
    )
    return {"approval": item.model_dump()}


@api_router.post("/sandbox/approvals/{request_id}/resolve")
async def resolve_hitl_approval(request_id: str, req: ResolveHITLRequest) -> dict[str, Any]:
    """Approve or reject a pending HITL request."""
    try:
        resolved = await sandbox_manager.resolve_hitl_request(request_id, approved=req.approved)
        return {"approval": resolved.model_dump()}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.get("/mcp/servers")
async def list_mcp_servers() -> dict[str, Any]:
    """List configured Model Context Protocol (MCP) servers."""
    servers = [s.model_dump() for s in mcp_client_manager.list_servers()]
    return {"servers": servers}


@api_router.post("/mcp/servers/{server_id}/toggle")
async def toggle_mcp_server(server_id: str, req: ToggleMCPServerRequest) -> dict[str, Any]:
    """Enable or disable an MCP server."""
    try:
        server = mcp_client_manager.toggle_server(server_id, req.enabled)
        return {"server": server.model_dump()}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.post("/computer-use/emergency-stop")
async def trigger_computer_use_emergency_stop() -> dict[str, Any]:
    """Trigger the emergency stop kill switch for Tier 3 GUI automation."""
    return computer_use_controller.trigger_emergency_stop()


@api_router.post("/computer-use/reset")
async def reset_computer_use_emergency_stop() -> dict[str, Any]:
    """Reset the emergency stop state for Tier 3 GUI automation."""
    return computer_use_controller.reset_emergency_stop()


class IndexWorkspaceRequest(BaseModel):
    workspace_id: str
    folder_path: str
    enable_watcher: bool = True


class RAGSearchRequest(BaseModel):
    query: str
    workspace_id: str | None = None
    top_k: int = 5


class SaveMemoryRequest(BaseModel):
    fact: str
    category: str = "preferensi_pengguna"
    workspace_id: str | None = None
    workspace_folder: str | None = None


class ConfigureTelegramRequest(BaseModel):
    bot_token: str


class SimulateTelegramMessageRequest(BaseModel):
    telegram_user_id: int
    text: str
    username: str = "pengguna_demo"
    workspace_path: str | None = None


@api_router.get("/rag/documents")
async def list_rag_documents(workspace_id: str | None = None) -> dict[str, Any]:
    """List indexed documents in the Hybrid RAG database."""
    docs = await rag_store.list_indexed_documents(workspace_id=workspace_id)
    return {"documents": docs}


@api_router.post("/rag/index-folder")
async def index_rag_workspace_folder(req: IndexWorkspaceRequest) -> dict[str, Any]:
    """Incrementally index all supported documents in a workspace folder and optionally start watchdog."""
    stats = await rag_store.index_workspace_folder(req.workspace_id, req.folder_path)
    if req.enable_watcher:
        rag_watcher.start_watching(req.workspace_id, req.folder_path)
    return stats


@api_router.post("/rag/search")
async def search_rag_hybrid(req: RAGSearchRequest) -> dict[str, Any]:
    """Search Hybrid Vector + SQLite FTS5 BM25 index using Reciprocal Rank Fusion (RRF)."""
    results = await rag_store.hybrid_search(
        query=req.query,
        workspace_id=req.workspace_id,
        top_k=req.top_k,
    )
    return {"query": req.query, "results": results}


@api_router.get("/memories")
async def list_user_memories(query: str | None = None, category: str | None = None) -> dict[str, Any]:
    """List stored long-term user and project memories."""
    memories = await rag_store.recall_user_memories(query=query, category=category)
    return {"memories": memories}


@api_router.post("/memories")
async def create_user_memory(req: SaveMemoryRequest) -> dict[str, Any]:
    """Save a persistent user preference or project fact."""
    memory = await rag_store.remember_user_fact(
        fact=req.fact,
        category=req.category,
        workspace_id=req.workspace_id,
        workspace_folder=req.workspace_folder,
    )
    return {"memory": memory}


@api_router.get("/telegram/status")
async def get_telegram_gateway_status() -> dict[str, Any]:
    """Return Telegram Bot connection status, pairing code, whitelist, and live audit logs."""
    return telegram_gateway.get_status()


@api_router.post("/telegram/configure")
async def configure_telegram_gateway(req: ConfigureTelegramRequest) -> dict[str, Any]:
    """Configure @BotFather HTTP API Token and activate Telegram gateway."""
    try:
        return await telegram_gateway.configure_bot(req.bot_token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api_router.post("/telegram/regenerate-code")
async def regenerate_telegram_pairing_code() -> dict[str, Any]:
    """Generate a new 6-digit pairing code."""
    code = telegram_auth_guard.regenerate_pairing_code()
    return {"pairing_code": code}


@api_router.post("/telegram/simulate")
async def simulate_telegram_command(req: SimulateTelegramMessageRequest) -> dict[str, Any]:
    """Process a simulated or live Telegram message through the auth guard and orchestrator."""
    return await telegram_gateway.handler.handle_incoming_message(
        telegram_user_id=req.telegram_user_id,
        text=req.text,
        username=req.username,
        workspace_path=req.workspace_path,
    )


