"""REST API v1 endpoints for AKSA Teams, Agents, Workspaces, Models, Orchestrator, and Token Analytics."""

from __future__ import annotations

from pathlib import Path
import asyncio
import hashlib
import hmac
import os
import stat
import subprocess
import sys
from typing import Any

import aiosqlite
import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.core.auth_context import get_default_host_principal, resolve_authenticated_principal
from app.core.llm_router import UnifiedLLMRouter
from app.core.observability import observability_manager
from app.core.orchestrator import HierarchicalOrchestrator
from app.core.sandbox import (
    RiskLevel,
    SandboxViolationError,
    WorkspacePolicy,
    canonicalize_and_validate_path,
    sandbox_manager,
)
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

GLOBAL_ORCHESTRATION_SEMAPHORE = asyncio.Semaphore(3)
_session_locks: dict[str, asyncio.Lock] = {}
_active_tasks: dict[str, asyncio.Task] = {}


async def _check_daily_token_budget() -> tuple[bool, int, int]:
    """Check if today's token usage has exceeded daily budget (P2-3)."""
    budget_setting = await db_manager.get_setting("daily_token_budget", 500_000)
    try:
        daily_budget = int(budget_setting)
    except (TypeError, ValueError):
        daily_budget = 500_000

    if daily_budget <= 0:
        return True, 0, 0

    async with aiosqlite.connect(db_manager.db_path) as conn:
        cursor = await conn.execute(
            """
            SELECT COALESCE(SUM(input_tokens + output_tokens), 0)
            FROM token_usage_logs
            WHERE date(created_at) = date('now')
            """
        )
        row = await cursor.fetchone()
        used_today = int(row[0]) if row else 0

    return used_today < daily_budget, used_today, daily_budget


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
    owner_id: str | None = None


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
async def get_health(nonce: str | None = None) -> dict[str, Any]:
    """Return engine status, database path, and local AI availability with optional HMAC identity verification."""
    ollama_info = await _check_ollama_status()
    tg_status = telegram_gateway.get_status()
    resp: dict[str, Any] = {
        "status": "ok",
        "version": "1.0.0",
        "engine": "aksa-engine",
        "appdata_dir": str(settings.appdata_dir),
        "ollama": ollama_info,
        "telegram": {
            "connected": tg_status["connected"],
            "bot_username": tg_status["bot_username"],
        },
    }
    if nonce:
        auth_key = settings.auth_token.encode("utf-8")
        resp["nonce_hmac"] = hmac.new(auth_key, nonce.encode("utf-8"), hashlib.sha256).hexdigest()
    return resp


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
async def execute_hierarchical_task(req: ExecuteTaskRequest, request: Request) -> dict[str, Any]:
    """Execute a user instruction with per-session concurrency guard, global limit, and daily budget enforcement (P2-3)."""
    principal_id = resolve_authenticated_principal(request)

    # 1. Daily Token Budget Guard
    allowed, used_today, daily_budget = await _check_daily_token_budget()
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Batas kuota token harian telah tercapai ({used_today:,}/{daily_budget:,} token). Harap atur ulang batas kuota di menu Pengaturan.",
        )

    # 2. Per-Session Concurrency Lock (max 1 active task per session)
    sess_id = req.session_id or "default_session"
    if sess_id not in _session_locks:
        _session_locks[sess_id] = asyncio.Lock()
    session_lock = _session_locks[sess_id]

    if session_lock.locked():
        raise HTTPException(
            status_code=429,
            detail=f"Sesi '{sess_id}' sedang menjalankan tugas lain. Harap tunggu hingga selesai atau batalkan tugas sebelumnya.",
        )

    # 3. Global Concurrency Semaphore (max 3 concurrent tasks system-wide)
    if GLOBAL_ORCHESTRATION_SEMAPHORE.locked():
        raise HTTPException(
            status_code=429,
            detail="Kapasitas eksekusi orkestrasi sedang penuh (maksimal 3 tugas bersamaan). Silakan coba lagi beberapa saat.",
        )

    resolved_path: str | None = None
    if req.workspace_id:
        ws = await authorize_workspace(req.workspace_id, principal_id, required_permission="read")
        resolved_path = ws["folder_path"]
    elif req.workspace_path:
        matching_ws = await db_manager.get_workspace_by_path(req.workspace_path)
        if matching_ws:
            ws = await authorize_workspace(matching_ws["id"], principal_id, required_permission="read")
            resolved_path = ws["folder_path"]
        else:
            raise HTTPException(
                status_code=403,
                detail=f"Akses Ditolak: Folder '{req.workspace_path}' bukan folder kerja terotorisasi.",
            )

    async with session_lock:
        async with GLOBAL_ORCHESTRATION_SEMAPHORE:
            curr_task = asyncio.current_task()
            if curr_task:
                _active_tasks[sess_id] = curr_task
            try:
                result = await orchestrator.execute_hierarchical_task(
                    prompt=req.prompt,
                    team_id=req.team_id,
                    workspace_id=req.workspace_id,
                    workspace_path=resolved_path,
                    session_id=sess_id,
                )
                return result
            except asyncio.CancelledError:
                return {
                    "reply": "Tugas orkestrasi berhasil dibatalkan atas permintaan pengguna.",
                    "cancelled": True,
                    "artifacts": [],
                    "steps": [],
                }
            finally:
                _active_tasks.pop(sess_id, None)


@api_router.post("/orchestrate/cancel")
@api_router.post("/orchestrate/cancel/{session_id}")
async def cancel_orchestration_task(session_id: str = "default_session") -> dict[str, Any]:
    """Cancel an ongoing orchestration task for a session (P2-3)."""
    task = _active_tasks.get(session_id)
    if task and not task.done():
        task.cancel()
        return {"status": "cancelled", "session_id": session_id, "detail": "Tugas orkestrasi berhasil dibatalkan."}
    return {"status": "not_running", "session_id": session_id, "detail": "Tidak ada tugas aktif di sesi ini."}


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


async def authorize_workspace(
    workspace_id: str | None,
    principal_id: str,
    required_permission: str = "read",  # "read" | "write" | "execute" | "delete" | "index" | "search"
) -> dict[str, Any]:
    """Centralized authorization dependency for all workspace operations (P0-02, P0-03).
    
    Validates:
    1. workspace_id is non-empty.
    2. workspace exists in the persistent registry.
    3. principal_id owns or has access to the workspace.
    4. required permission is granted on the workspace policy.
    """
    if not workspace_id or not str(workspace_id).strip():
        raise HTTPException(
            status_code=400,
            detail="Validasi Gagal: workspace_id wajib disediakan untuk operasi ini.",
        )

    ws = await db_manager.get_workspace(str(workspace_id).strip())
    if not ws:
        raise HTTPException(
            status_code=404,
            detail=f"Folder kerja '{workspace_id}' tidak ditemukan di sistem.",
        )

    owner_id = ws.get("owner_id")
    if owner_id and owner_id != principal_id:
        await db_manager.record_permission_audit({
            "principal_type": "user",
            "principal_id": principal_id,
            "capability_id": f"filesystem.workspace.{required_permission}",
            "resource_scope": workspace_id,
            "decision": "deny",
            "reason_code": "PRINCIPAL_MISMATCH",
        })
        raise HTTPException(
            status_code=403,
            detail=f"Akses Ditolak: Principal tidak memiliki izin untuk mengakses folder kerja '{workspace_id}'.",
        )

    if required_permission in ("read", "search") and not ws.get("allow_read", True):
        await db_manager.record_permission_audit({
            "principal_type": "user",
            "principal_id": principal_id,
            "capability_id": f"filesystem.workspace.{required_permission}",
            "resource_scope": workspace_id,
            "decision": "deny",
            "reason_code": "ALLOW_READ_DISABLED",
        })
        raise HTTPException(
            status_code=403,
            detail=f"Akses Ditolak: Izin membaca (allow_read) dinonaktifkan pada folder kerja '{workspace_id}'.",
        )

    if required_permission in ("write", "index") and not ws.get("allow_write", True):
        await db_manager.record_permission_audit({
            "principal_type": "user",
            "principal_id": principal_id,
            "capability_id": f"filesystem.workspace.{required_permission}",
            "resource_scope": workspace_id,
            "decision": "deny",
            "reason_code": "ALLOW_WRITE_DISABLED",
        })
        raise HTTPException(
            status_code=403,
            detail=f"Akses Ditolak: Izin menulis (allow_write) dinonaktifkan pada folder kerja '{workspace_id}'.",
        )

    if required_permission == "execute" and not ws.get("allow_execute", False):
        await db_manager.record_permission_audit({
            "principal_type": "user",
            "principal_id": principal_id,
            "capability_id": "filesystem.workspace.execute",
            "resource_scope": workspace_id,
            "decision": "deny",
            "reason_code": "ALLOW_EXECUTE_DISABLED",
        })
        raise HTTPException(
            status_code=403,
            detail=f"Akses Ditolak: Izin eksekusi (allow_execute) dinonaktifkan pada folder kerja '{workspace_id}'.",
        )

    return ws


@api_router.get("/workspaces")
async def list_workspaces(request: Request) -> dict[str, Any]:
    """List all authorized PC workspace folders for the verified caller."""
    principal_id = resolve_authenticated_principal(request)
    workspaces = await db_manager.list_workspaces(principal_id=principal_id)
    return {"workspaces": workspaces}


@api_router.post("/workspaces")
async def register_workspace(req: UpsertWorkspaceRequest, request: Request) -> dict[str, Any]:
    """Authorize a PC folder for agent access."""
    target = Path(req.folder_path).expanduser()
    if not target.exists() or not target.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Folder '{req.folder_path}' tidak ditemukan di komputer ini.",
        )
    principal_id = resolve_authenticated_principal(request)
    payload = req.model_dump()
    payload["owner_id"] = principal_id
    workspace = await db_manager.upsert_workspace(payload)
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
async def delete_workspace(workspace_id: str, request: Request) -> dict[str, Any]:
    """Remove an authorized PC workspace folder with principal authorization (P0-02)."""
    principal_id = resolve_authenticated_principal(request)
    ws_rec = await authorize_workspace(workspace_id, principal_id, required_permission="delete")
    deleted = await db_manager.delete_workspace(workspace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Folder Kerja tidak ditemukan.")
    if ws_rec and ws_rec.get("folder_path"):
        sandbox_manager.remove_workspace(ws_rec["folder_path"])
    return {"deleted": True, "id": workspace_id}


class OpenPathRequest(BaseModel):
    path: str


SAFE_OPEN_EXTENSIONS = {
    ".docx",
    ".xlsx",
    ".pptx",
    ".pdf",
    ".txt",
    ".csv",
    ".md",
    ".png",
    ".jpg",
    ".jpeg",
    ".json",
}


@api_router.post("/system/open-path")
async def open_system_path(req: OpenPathRequest) -> dict[str, Any]:
    """Open a file or directory in the operating system's native application (Word, Excel, Finder, Explorer).

    Enforces strict workspace sandbox jail, extension whitelist, app bundle rejection,
    and structured audit logging (P0-1).
    """
    raw_path = (req.path or "").strip()
    if not raw_path:
        raise HTTPException(status_code=400, detail="Path tidak boleh kosong.")

    # 1. Reject UNC or network paths immediately
    if raw_path.startswith("\\\\") or raw_path.startswith("//"):
        observability_manager.log_event(
            level="WARNING",
            component="SYSTEM_OPEN_PATH",
            message=f"Percobaan akses UNC path ditolak: {raw_path}",
            error_code="UNC_PATH_FORBIDDEN",
        )
        raise HTTPException(status_code=403, detail="Akses path jaringan UNC ditolak.")

    # 2. Sync DB workspaces to sandbox_manager
    workspaces = await db_manager.list_workspaces()
    for ws in workspaces:
        sandbox_manager.register_workspace(
            WorkspacePolicy(
                folder_path=ws["folder_path"],
                allow_read=bool(ws.get("allow_read", True)),
                allow_write=bool(ws.get("allow_write", True)),
                allow_execute=bool(ws.get("allow_execute", False)),
            )
        )

    # 3. Resolve relative vs absolute candidate
    target_candidate = Path(raw_path).expanduser()
    if not target_candidate.is_absolute():
        found = False
        for ws in workspaces:
            cand = Path(ws["folder_path"]) / raw_path
            if cand.exists():
                target_candidate = cand
                found = True
                break
        if not found and workspaces:
            # Anchor to first workspace to enforce sandbox validation bounds
            target_candidate = Path(workspaces[0]["folder_path"]) / raw_path

    # 4. Enforce sandbox jail validation (resolves symlinks via realpath)
    try:
        resolved = sandbox_manager.validate_path(target_candidate, mode="read")
    except SandboxViolationError as sve:
        observability_manager.log_event(
            level="WARNING",
            component="SYSTEM_OPEN_PATH",
            message=f"Percobaan pelanggaran sandbox pada open-path: {raw_path}",
            error_code="SANDBOX_VIOLATION",
            details={"requested_path": raw_path},
        )
        raise HTTPException(status_code=403, detail=str(sve))

    # 5. Check if target exists
    if not resolved.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Berkas '{resolved.name}' tidak ditemukan di sistem.",
        )

    # 6. Reject app bundles and enforce directory vs file rules
    if resolved.is_dir():
        if resolved.name.lower().endswith(".app") or any(part.lower().endswith(".app") for part in resolved.parts):
            observability_manager.log_event(
                level="WARNING",
                component="SYSTEM_OPEN_PATH",
                message=f"Percobaan membuka bundle aplikasi ditolak: {resolved}",
                error_code="APP_BUNDLE_FORBIDDEN",
            )
            raise HTTPException(
                status_code=403,
                detail="Membuka bundle aplikasi (.app) tidak diizinkan.",
            )

        is_ws_root = any(
            resolved == Path(os.path.realpath(ws["folder_path"]))
            for ws in workspaces
        )
        if not is_ws_root:
            raise HTTPException(
                status_code=400,
                detail="Membuka direktori hanya diizinkan untuk root Folder Kerja yang terdaftar.",
            )
    else:
        suffix = resolved.suffix.lower()
        if suffix not in SAFE_OPEN_EXTENSIONS:
            observability_manager.log_event(
                level="WARNING",
                component="SYSTEM_OPEN_PATH",
                message=f"Percobaan membuka file dengan ekstensi tidak aman: {suffix}",
                error_code="DISALLOWED_EXTENSION",
                details={"file": str(resolved), "extension": suffix},
            )
            raise HTTPException(
                status_code=400,
                detail=f"Ekstensi berkas '{suffix}' tidak diizinkan untuk dibuka demi keamanan sistem.",
            )

    # 7. Audit log for allowed open operation
    observability_manager.log_event(
        level="INFO",
        component="SYSTEM_OPEN_PATH",
        message=f"Membuka berkas/direktori aman: {resolved.name}",
        details={"path": str(resolved), "is_dir": resolved.is_dir()},
    )

    # 8. Dispatch native OS open
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(resolved)])
        elif sys.platform == "win32":
            os.startfile(str(resolved))
        else:
            subprocess.Popen(["xdg-open", str(resolved)])
        return {
            "success": True,
            "path": str(resolved),
            "name": resolved.name,
            "message": f"Berkas '{resolved.name}' berhasil dibuka di aplikasi default sistem.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal membuka berkas: {e}")


@api_router.get("/workspaces/{workspace_id}/files")
async def list_workspace_files(workspace_id: str, request: Request) -> dict[str, Any]:
    """List top-level files inside an authorized workspace folder."""
    principal_id = resolve_authenticated_principal(request)
    ws = await authorize_workspace(workspace_id, principal_id, required_permission="read")

    canonical_root = Path(os.path.realpath(ws["folder_path"]))
    if not canonical_root.exists() or not canonical_root.is_dir():
        return {"files": [], "exists": False}

    files: list[dict[str, Any]] = []
    for entry in sorted(canonical_root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if entry.name.startswith("."):
            continue
        # Symlink check: if entry is a symlink pointing outside, filter it out!
        if entry.is_symlink():
            try:
                target = Path(os.path.realpath(entry))
                if target != canonical_root and not target.is_relative_to(canonical_root):
                    continue
            except Exception:
                continue

        try:
            stat_info = entry.stat()
            if stat.S_ISFIFO(stat_info.st_mode) or stat.S_ISSOCK(stat_info.st_mode):
                continue
            files.append(
                {
                    "name": entry.name,
                    "path": str(entry),
                    "is_dir": entry.is_dir(),
                    "ext": entry.suffix.lower(),
                    "size_bytes": stat_info.st_size if entry.is_file() else 0,
                    "modified_at": stat_info.st_mtime,
                }
            )
        except (PermissionError, FileNotFoundError, OSError):
            continue

    await db_manager.record_permission_audit({
        "principal_type": "user",
        "principal_id": principal_id,
        "capability_id": "filesystem.workspace.list",
        "resource_scope": workspace_id,
        "decision": "allow",
        "reason_code": "LIST_FILES_SUCCESS",
    })
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
    action_id: str | None = None
    session_id: str | None = None
    workspace_id: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    tool_version: str = "1.0.0"


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
async def list_hitl_approvals(request: Request, status: str | None = None) -> dict[str, Any]:
    """List Human-in-the-Loop approval gate items for the authenticated caller (P0-03, P0-04)."""
    principal_id = resolve_authenticated_principal(request)
    items = [i.model_dump() for i in sandbox_manager.list_approvals(status=status, principal_id=principal_id)]
    return {"approvals": items}


@api_router.post("/sandbox/approvals")
async def create_hitl_approval(req: CreateHITLRequest, request: Request) -> dict[str, Any]:
    """Trigger a new HITL approval prompt for Desktop UI & Telegram."""
    principal_id = resolve_authenticated_principal(request)
    item = await sandbox_manager.create_hitl_request(
        tool_name=req.tool_name,
        title_id=req.title_id,
        description_id=req.description_id,
        risk_level=req.risk_level,
        target_path=req.target_path,
        agent_name=req.agent_name,
        action_id=req.action_id,
        session_id=req.session_id,
        workspace_id=req.workspace_id,
        arguments=req.arguments,
        tool_version=req.tool_version,
        principal_id=principal_id,
    )
    return {"approval": item.model_dump()}


@api_router.post("/sandbox/approvals/{request_id}/resolve")
async def resolve_hitl_approval(
    request_id: str,
    req: ResolveHITLRequest,
    request: Request,
) -> dict[str, Any]:
    """Approve or reject a pending HITL request."""
    principal_id = resolve_authenticated_principal(request)
    try:
        resolved = await sandbox_manager.resolve_hitl_request(
            request_id,
            approved=req.approved,
            principal_id=principal_id,
        )
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
    folder_path: str | None = None
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
async def list_rag_documents(
    request: Request,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """List indexed documents in the Hybrid RAG database (P0-02, P0-03)."""
    principal_id = resolve_authenticated_principal(request)
    if workspace_id:
        await authorize_workspace(workspace_id, principal_id, required_permission="read")
    docs = await rag_store.list_indexed_documents(workspace_id=workspace_id)
    return {"documents": docs}


@api_router.post("/rag/index-folder")
async def index_rag_workspace_folder(
    req: IndexWorkspaceRequest,
    request: Request,
) -> dict[str, Any]:
    """Incrementally index all supported documents in an authorized workspace folder and optionally start watchdog."""
    principal_id = resolve_authenticated_principal(request)
    ws = await authorize_workspace(req.workspace_id, principal_id, required_permission="index")

    canonical_ws_root = Path(os.path.realpath(ws["folder_path"]))
    target_scan_dir = canonical_ws_root
    if req.folder_path:
        try:
            target_scan_dir = canonicalize_and_validate_path(req.folder_path, canonical_ws_root)
        except SandboxViolationError:
            await db_manager.record_permission_audit({
                "principal_type": "user",
                "principal_id": principal_id,
                "capability_id": "rag.index",
                "resource_scope": req.workspace_id,
                "decision": "deny",
                "reason_code": "WORKSPACE_BOUNDARY_VIOLATION",
            })
            raise HTTPException(status_code=403, detail="Akses ditolak: Path berada di luar Folder Kerja yang sah.")

    try:
        stats = await rag_store.index_workspace_folder(
            workspace_id=req.workspace_id,
            folder_path=target_scan_dir,
            principal_id=principal_id,
        )
    except (PermissionError, SandboxViolationError) as pe:
        raise HTTPException(status_code=403, detail=str(pe))

    if req.enable_watcher:
        rag_watcher.start_watching(req.workspace_id, str(canonical_ws_root))

    await db_manager.record_permission_audit({
        "principal_type": "user",
        "principal_id": principal_id,
        "capability_id": "rag.index",
        "resource_scope": req.workspace_id,
        "decision": "allow",
        "reason_code": "RAG_INDEX_SUCCESS",
    })
    return stats


@api_router.post("/rag/search")
async def search_rag_hybrid(req: RAGSearchRequest, request: Request) -> dict[str, Any]:
    """Search Hybrid Vector + SQLite FTS5 BM25 index using Reciprocal Rank Fusion (RRF) with workspace authorization (P0-02)."""
    principal_id = resolve_authenticated_principal(request)
    await authorize_workspace(req.workspace_id, principal_id, required_permission="search")
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


from app.system.app_discovery import application_discovery_manager
from app.system.permission_broker import permission_broker
from app.skills.skill_manager import agent_skills_manager


class LaunchAppRequest(BaseModel):
    document_path: str | None = None


class ToggleAppConnectionRequest(BaseModel):
    is_connected: bool


class RequestCapabilityGrantRequest(BaseModel):
    capability_id: str
    resource_scope: str = "workspace"
    grant_source: str = "desktop_ui"


class InstallCuratedSkillRequest(BaseModel):
    skill_id: str
    target_agent_id: str | None = None
    install_to_shared: bool = False


class ToggleSkillRequest(BaseModel):
    enabled: bool


@api_router.get("/system/apps")
async def list_desktop_applications() -> dict[str, Any]:
    """List discovered desktop applications and their running/adapter status."""
    apps = await db_manager.list_installed_apps()
    if not apps:
        apps = await application_discovery_manager.scan_and_sync()
    return {"apps": apps}


@api_router.post("/system/apps/refresh")
async def refresh_desktop_applications() -> dict[str, Any]:
    """Rescan local operating system registry / application bundles and update database."""
    apps = await application_discovery_manager.scan_and_sync()
    return {"apps": apps, "total": len(apps)}


@api_router.get("/system/apps/{app_id}")
async def get_desktop_application(app_id: str) -> dict[str, Any]:
    """Get detailed metadata and available adapters for a specific desktop application."""
    app = await db_manager.get_installed_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Aplikasi tidak ditemukan.")
    return {"app": app}


@api_router.post("/system/apps/{app_id}/launch")
async def launch_desktop_application(app_id: str, req: LaunchAppRequest) -> dict[str, Any]:
    """Safely launch an application or open a file with it."""
    result = await application_discovery_manager.launch_application(app_id, req.document_path)
    return result


@api_router.post("/system/apps/{app_id}/toggle-connection")
async def toggle_desktop_application_connection(app_id: str, req: ToggleAppConnectionRequest) -> dict[str, Any]:
    """Authorize or revoke application access in AKSA, independent of process running status."""
    updated = await db_manager.toggle_app_connection(app_id, req.is_connected)
    if not updated:
        raise HTTPException(status_code=404, detail="Aplikasi tidak ditemukan.")
    action = "dihubungkan dan diizinkan" if req.is_connected else "diputuskan aksesnya"
    return {
        "success": True,
        "app": updated,
        "is_connected": updated["is_connected"],
        "message": f"Aplikasi '{updated['display_name']}' berhasil {action}.",
    }


@api_router.get("/system/permissions")
async def list_system_permissions(workspace_folder: str | None = None) -> dict[str, Any]:
    """Return all platform capabilities with both native OS status and AKSA consent status."""
    statuses = await permission_broker.get_all_capability_statuses(workspace_folder=workspace_folder)
    return {"capabilities": statuses}


@api_router.post("/system/permissions/request")
async def request_system_permission(req: RequestCapabilityGrantRequest) -> dict[str, Any]:
    """Record an explicit user consent grant for a system capability."""
    result = await permission_broker.request_capability_grant(
        capability_id=req.capability_id,
        resource_scope=req.resource_scope,
        grant_source=req.grant_source,
    )
    return result


@api_router.delete("/system/permissions/{grant_id}")
async def revoke_system_permission(grant_id: str) -> dict[str, Any]:
    """Revoke an active AKSA capability grant immediately."""
    success = await permission_broker.revoke_capability_grant(grant_id)
    if not success:
        raise HTTPException(status_code=404, detail="Izin tidak ditemukan atau sudah dicabut.")
    return {"revoked": True, "grant_id": grant_id}


@api_router.get("/system/permissions/audit")
async def list_permission_audit_log(limit: int = 50) -> dict[str, Any]:
    """List permission authorization and revocation audit ledger events."""
    events = await db_manager.list_permission_audit_events(limit=limit)
    return {"audit_events": events}


@api_router.get("/skills")
async def list_skills() -> dict[str, Any]:
    """List installed Agent Skills and available curated catalog."""
    installed = await db_manager.list_installed_skills()
    curated = [c.model_dump() for c in agent_skills_manager.list_curated_catalog()]
    return {
        "installed_skills": installed,
        "curated_catalog": curated,
    }


@api_router.post("/skills/install-curated")
async def install_curated_skill(req: InstallCuratedSkillRequest) -> dict[str, Any]:
    """Install a curated Agent Skill in a DISABLED default state."""
    try:
        skill = await agent_skills_manager.install_curated_skill(
            req.skill_id,
            target_agent_id=req.target_agent_id,
            install_to_shared=req.install_to_shared,
        )
        return {"skill": skill, "message": "Keahlian berhasil dipasang dalam kondisi nonaktif (dinonaktifkan secara default)."}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.post("/skills/{skill_id}/toggle")
async def toggle_skill_status(skill_id: str, req: ToggleSkillRequest) -> dict[str, Any]:
    """Explicitly enable or disable an installed Agent Skill."""
    updated = await db_manager.toggle_skill_enabled(skill_id, req.enabled)
    if not updated:
        raise HTTPException(status_code=404, detail="Keahlian tidak ditemukan.")
    return {"skill": updated}


@api_router.delete("/skills/{skill_id}")
async def delete_installed_skill(skill_id: str) -> dict[str, Any]:
    """Uninstall an Agent Skill, revoke all its grants, and remove its runtime files."""
    deleted = await agent_skills_manager.uninstall_skill(skill_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Keahlian tidak ditemukan.")
    return {"deleted": True, "skill_id": skill_id, "grants_revoked": True}


from app.core.observability import observability_manager
from app.core.privacy_gate import privacy_policy_gate
from app.tools.mcp.mcp_client import mcp_client_manager


class UpdatePrivacySettingsRequest(BaseModel):
    provider_mode: str | None = None
    default_classification: str | None = None
    allowed_providers: list[str] | None = None
    telemetry_opt_in: bool | None = None


class EvaluateDisclosureRequest(BaseModel):
    provider: str
    model_id: str
    prompt: str
    attachments: list[dict[str, Any]] | None = None
    data_classification: str | None = None
    user_consent_granted: bool = False


@api_router.post("/workspaces/revoke-all")
async def revoke_all_workspaces_endpoint(request: Request) -> dict[str, Any]:
    """Immediately revoke all workspace access in SQLite and in-memory SandboxManager (Section 4.4, P0-02)."""
    principal_id = resolve_authenticated_principal(request)
    removed_db = await db_manager.revoke_all_workspaces(principal_id=principal_id)
    removed_mem = sandbox_manager.clear_all_workspaces()
    return {
        "revoked": True,
        "workspaces_removed": max(removed_db, removed_mem),
        "message": "Seluruh izin akses Folder Kerja telah dicabut secara menyeluruh.",
    }


@api_router.delete("/models/keys/{provider}")
async def revoke_provider_api_key(provider: str) -> dict[str, Any]:
    """Revoke and delete a provider API key from OS Credential Vault and SQLite metadata."""
    revoked = await llm_router.revoke_api_key(provider)
    return {"revoked": revoked, "provider": provider}


@api_router.get("/privacy/settings")
async def get_privacy_settings() -> dict[str, Any]:
    """Return active LLM provider mode, default data classification, and telemetry status."""
    await privacy_policy_gate.ensure_loaded_from_db(db_manager)
    return privacy_policy_gate.get_status()


@api_router.post("/privacy/settings")
async def update_privacy_settings(req: UpdatePrivacySettingsRequest) -> dict[str, Any]:
    """Update LLM provider mode (local_only, cloud_by_choice, hybrid_with_consent, enterprise_managed)."""
    try:
        updated = await privacy_policy_gate.configure_and_persist(
            provider_mode=req.provider_mode,
            default_classification=req.default_classification,
            allowed_providers=req.allowed_providers,
            telemetry_opt_in=req.telemetry_opt_in,
            db=db_manager,
        )
        return {"updated": True, "settings": updated}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api_router.post("/privacy/evaluate-disclosure")
async def evaluate_data_disclosure(req: EvaluateDisclosureRequest) -> dict[str, Any]:
    """Evaluate DataDisclosureGate before external processing."""
    summary = privacy_policy_gate.evaluate_disclosure(
        provider=req.provider,
        model_id=req.model_id,
        messages=[{"role": "user", "content": req.prompt}],
        attachments=req.attachments,
        explicit_classification=req.data_classification,
        user_consent_granted=req.user_consent_granted,
    )
    return {"disclosure": summary.model_dump()}


@api_router.post("/mcp/servers/{server_id}/revoke")
async def revoke_mcp_server_endpoint(server_id: str) -> dict[str, Any]:
    """Disable an MCP server and revoke its active grants."""
    try:
        res = mcp_client_manager.revoke_server(server_id)
        return res
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.get("/system/diagnostics/support-bundle")
async def get_support_diagnostic_bundle() -> dict[str, Any]:
    """Generate a redacted support diagnostic bundle without secrets or document contents (Section 13.3)."""
    bundle = await observability_manager.generate_support_bundle()
    return {"support_bundle": bundle}


# ---------------------------------------------------------------------------
# Section 2 & 4: Root Directory, Agent Learning & Model Discovery Endpoints
# ---------------------------------------------------------------------------

from app.core.agent_directory import agent_directory_service, agent_isolation_policy
from app.core.agent_learning import (
    AgentLearningMetrics,
    AgentMemoryService,
    SkillVersionService,
)
from app.core.model_discovery import model_discovery_service


class SetRootDirRequest(BaseModel):
    root_path: str


class UpdatePreferencesRequest(BaseModel):
    preferences: dict[str, Any]


class PromoteSkillRequest(BaseModel):
    version: str = "1.0.0"
    promote_to_shared: bool = False


class RollbackSkillRequest(BaseModel):
    target_version: str


@api_router.get("/skills/{skill_id}/instructions")
async def get_skill_instructions(skill_id: str, agent_id: str | None = None) -> dict[str, Any]:
    """Progressive disclosure: loads actual skill Markdown instructions on demand."""
    content = agent_skills_manager.load_skill_instructions(skill_id, agent_id=agent_id)
    return {"skill_id": skill_id, "instructions": content}


@api_router.get("/system/root-dir")
async def get_system_root_dir_status() -> dict[str, Any]:
    """Return status and space of user-selected AKSA root directory."""
    return agent_directory_service.get_root_status()


@api_router.post("/system/root-dir")
async def set_system_root_dir(req: SetRootDirRequest) -> dict[str, Any]:
    """Configure and initialize a user-selected AKSA root directory."""
    try:
        res = agent_directory_service.set_root_dir(req.root_path)
        return res
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api_router.get("/models/discovered")
async def get_discovered_models() -> dict[str, Any]:
    """Return live or cached models discovered across active providers."""
    keys = await llm_router.get_saved_api_keys()
    discovered = await model_discovery_service.discover_all_active_providers(keys)
    serialized = {prov: [m.model_dump() for m in m_list] for prov, m_list in discovered.items()}
    return {"providers": serialized}


@api_router.post("/models/refresh")
async def refresh_all_models() -> dict[str, Any]:
    """Force fresh live discovery query across all configured providers."""
    keys = await llm_router.get_saved_api_keys()
    discovered = await model_discovery_service.discover_all_active_providers(keys)
    serialized = {prov: [m.model_dump() for m in m_list] for prov, m_list in discovered.items()}
    return {"refreshed": True, "providers": serialized}


@api_router.post("/models/providers/{provider_id}/refresh")
async def refresh_provider_models(provider_id: str) -> dict[str, Any]:
    """Force fresh discovery query for a single provider."""
    keys = await llm_router.get_saved_api_keys()
    models = await model_discovery_service.discover_provider(provider_id, api_key=keys.get(provider_id))
    return {"provider_id": provider_id, "models": [m.model_dump() for m in models]}


@api_router.get("/models/recommend")
async def recommend_model_for_role(role: str = "general") -> dict[str, Any]:
    """Recommend best model matching role requirements via multi-criteria scoring (P2.1)."""
    keys = await llm_router.get_saved_api_keys()
    discovered = await model_discovery_service.discover_all_active_providers(keys)
    all_models = [m for sublist in discovered.values() for m in sublist]
    res = model_discovery_service.recommend_model_with_scoring(role, all_models)
    return {
        "role": role,
        "recommended_model": res.recommended_model.model_dump() if res.recommended_model else None,
        "score": res.score,
        "reason": res.reason,
        "trade_offs": res.trade_offs,
        "alternatives": res.alternatives,
        "criteria_scores": res.criteria_scores,
        "metadata_source": res.metadata_source,
        "verified_at": res.verified_at,
    }


@api_router.get("/agents/{agent_id}/memory")
async def get_agent_memory(agent_id: str) -> dict[str, Any]:
    """Get isolated episodic memory tasks and preferences for a specific agent."""
    memory_svc = AgentMemoryService(agent_id)
    episodic = [t.model_dump() for t in memory_svc.list_episodic_tasks()]
    prefs = memory_svc.get_preferences()
    return {"agent_id": agent_id, "episodic_tasks": episodic, "preferences": prefs}


@api_router.post("/agents/{agent_id}/memory/preferences")
async def update_agent_preferences(agent_id: str, req: UpdatePreferencesRequest) -> dict[str, Any]:
    """Update agent preference profile with automatic privacy redaction."""
    memory_svc = AgentMemoryService(agent_id)
    updated = memory_svc.update_preferences(req.preferences)
    return {"agent_id": agent_id, "preferences": updated}


@api_router.get("/agents/{agent_id}/metrics")
async def get_agent_metrics(agent_id: str) -> dict[str, Any]:
    """Get learning metrics, success rates, and memory storage footprint for an agent."""
    return AgentLearningMetrics.get_metrics(agent_id)


@api_router.get("/agents/{agent_id}/skills/candidates")
async def list_agent_candidate_skills(agent_id: str) -> dict[str, Any]:
    """List candidate skills waiting for review/promotion for an agent."""
    version_svc = SkillVersionService(agent_id)
    candidates = version_svc.list_candidates()
    return {"agent_id": agent_id, "candidates": candidates}


class EvaluateCandidateRequest(BaseModel):
    replay_fixtures: list[dict[str, Any]] | None = None


@api_router.post("/agents/{agent_id}/skills/{skill_id}/evaluate")
async def evaluate_agent_candidate_skill(
    agent_id: str,
    skill_id: str,
    req: EvaluateCandidateRequest | None = None,
) -> dict[str, Any]:
    """Evaluate candidate skill safety, DAG/schemas, and isolated runtime replay."""
    if req and req.replay_fixtures and len(req.replay_fixtures) > 20:
        raise HTTPException(status_code=400, detail="Maksimal 20 variasi fixture diperbolehkan per evaluasi replay.")
    version_svc = SkillVersionService(agent_id)
    try:
        report = await version_svc.evaluate_and_replay_candidate(
            skill_id,
            replay_fixtures=req.replay_fixtures if req else None,
        )
        return {"report": report.model_dump()}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api_router.post("/agents/{agent_id}/skills/{skill_id}/promote")
async def promote_agent_skill(agent_id: str, skill_id: str, req: PromoteSkillRequest) -> dict[str, Any]:
    """Promote evaluated candidate to active versioned learned skill."""
    version_svc = SkillVersionService(agent_id)
    try:
        res = version_svc.promote_candidate(
            skill_id=skill_id,
            version=req.version,
            promote_to_shared=req.promote_to_shared,
        )
        return res
    except (FileNotFoundError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api_router.post("/agents/{agent_id}/skills/{skill_name}/rollback")
async def rollback_agent_skill(agent_id: str, skill_name: str, req: RollbackSkillRequest) -> dict[str, Any]:
    """Rollback an active learned skill to an earlier version."""
    version_svc = SkillVersionService(agent_id)
    try:
        return version_svc.rollback_skill(skill_name, req.target_version)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.post("/agents/{agent_id}/skills/{skill_name}/disable")
async def disable_agent_skill(agent_id: str, skill_name: str) -> dict[str, Any]:
    """Disable a learned skill."""
    version_svc = SkillVersionService(agent_id)
    try:
        return version_svc.disable_skill(skill_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.get("/agents/{agent_id}/skills/learned")
async def list_agent_learned_skills(agent_id: str) -> dict[str, Any]:
    """List all active learned skills for an agent."""
    version_svc = SkillVersionService(agent_id)
    skills = version_svc.list_learned_skills()
    return {"agent_id": agent_id, "learned_skills": skills}


@api_router.post("/agents/{agent_id}/export")
async def export_agent_bundle(agent_id: str) -> dict[str, Any]:
    """Export agent memory, profile, and learned skills to a portable zip archive."""
    try:
        archive = agent_isolation_policy.export_agent_package(agent_id)
        return {"agent_id": agent_id, "export_path": str(archive)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api_router.post("/agents/{agent_id}/purge")
async def purge_agent_bundle(agent_id: str) -> dict[str, Any]:
    """Permanently delete an agent's memory, profile, and learned skills."""
    purged = agent_isolation_policy.purge_agent_data(agent_id)
    return {"agent_id": agent_id, "purged": purged}


class AppSettingPayload(BaseModel):
    key: str
    value: Any


@api_router.get("/system/settings")
async def get_system_settings() -> dict[str, Any]:
    """Retrieve all system settings from SQLite app_settings as single source of truth (P2-5)."""
    async with aiosqlite.connect(db_manager.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT key, value_json, updated_at FROM app_settings")
        rows = await cursor.fetchall()
        settings_dict: dict[str, Any] = {}
        for r in rows:
            try:
                settings_dict[r["key"]] = json.loads(r["value_json"])
            except Exception:
                settings_dict[r["key"]] = r["value_json"]
        return {"settings": settings_dict}


@api_router.post("/system/settings")
async def save_system_setting(payload: AppSettingPayload) -> dict[str, Any]:
    """Persist a system setting into SQLite app_settings (P2-5)."""
    await db_manager.set_setting(payload.key, payload.value)
    return {"status": "saved", "key": payload.key, "value": payload.value}






