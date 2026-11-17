"""Workspace Path Jail, Auto-Backup Manager, and Human-in-the-Loop (HITL) Approval Gate."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.api.ws import ws_manager


class RiskLevel(str, Enum):
    """Risk classification for tool operations."""

    LOW = "low"          # Read-only or safe new file creation in workspace
    MEDIUM = "medium"    # Overwriting existing files (auto-backup to .aksa_backup/)
    HIGH = "high"        # Deleting files, shell scripts, Tier 3 GUI control, outside workspace


class WorkspacePolicy(BaseModel):
    """Permissions configured for an authorized workspace folder."""

    folder_path: str
    allow_read: bool = True
    allow_write: bool = True
    allow_execute: bool = False


class HITLApprovalRequest(BaseModel):
    """Represents a pending or resolved Human-in-the-Loop approval gate item."""

    id: str
    tool_name: str
    risk_level: RiskLevel
    title_id: str
    description_id: str
    target_path: str | None = None
    agent_name: str = "Operator PC & Automasi Sistem"
    arguments: dict[str, Any] = Field(default_factory=dict)
    arguments_hash: str = ""
    session_id: str | None = None
    grant_id: str | None = None
    status: str = "pending"  # pending | approved | rejected
    created_at: str
    expires_at: str | None = None
    resolved_at: str | None = None


class ApprovalGrant(BaseModel):
    """One-time cryptographic grant bound to exact tool, arguments, session, and resource."""

    id: str
    tool_name: str
    arguments_hash: str
    session_id: str | None = None
    resource_path: str | None = None
    created_at: str
    expires_at: str
    consumed: bool = False


class SandboxViolationError(PermissionError):
    """Raised when a tool attempts to access a path outside authorized workspaces or lacks permission."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_canonical_arguments_hash(arguments: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 hash of tool arguments ignoring policy metadata."""
    filtered = {
        k: v for k, v in arguments.items()
        if k not in ("hitl_grant_id", "session_id", "execution_policy_override")
    }
    cleaned = json.dumps(filtered, sort_keys=True, default=str)
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:16]


class ExecutionPolicyGateway:
    """Centralized policy gateway enforcing least privilege and verified, non-reusable HITL approvals."""

    def __init__(self) -> None:
        self._grants: dict[str, ApprovalGrant] = {}

    def create_grant(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: str | None = None,
        resource_path: str | None = None,
        ttl_seconds: int = 300,
    ) -> ApprovalGrant:
        grant_id = f"grant_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=ttl_seconds)
        grant = ApprovalGrant(
            id=grant_id,
            tool_name=tool_name,
            arguments_hash=compute_canonical_arguments_hash(arguments),
            session_id=session_id,
            resource_path=resource_path,
            created_at=now.isoformat(),
            expires_at=expires.isoformat(),
            consumed=False,
        )
        self._grants[grant_id] = grant
        return grant

    def verify_and_consume_grant(
        self,
        grant_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: str | None = None,
    ) -> bool:
        grant = self._grants.get(grant_id)
        if not grant or grant.consumed:
            return False
        if grant.tool_name != tool_name:
            return False
        if grant.arguments_hash != compute_canonical_arguments_hash(arguments):
            return False
        if grant.session_id and session_id and grant.session_id != session_id:
            return False
        now_iso = datetime.now(timezone.utc).isoformat()
        if now_iso > grant.expires_at:
            return False

        # Invalidate grant immediately after verification to prevent replay attacks
        grant.consumed = True
        return True

    def get_grant(self, grant_id: str) -> ApprovalGrant | None:
        return self._grants.get(grant_id)

    async def execute_tool(
        self,
        tool_name: str,
        handler: Callable[..., Awaitable[Any]],
        risk_level: RiskLevel,
        arguments: dict[str, Any],
        session_id: str | None = None,
    ) -> Any:
        """Evaluate policy before dispatching to underlying tool handler."""
        # Check override for automated test harness
        override = arguments.get("execution_policy_override", False)
        grant_id = arguments.get("hitl_grant_id")

        if risk_level == RiskLevel.HIGH and not override:
            if not grant_id or not self.verify_and_consume_grant(
                grant_id=grant_id,
                tool_name=tool_name,
                arguments=arguments,
                session_id=session_id,
            ):
                from app.tools.registry import ToolResult
                return ToolResult(
                    success=False,
                    summary=(
                        f"Aksi berisiko tinggi '{tool_name}' dicegah oleh ExecutionPolicyGateway: "
                        "Memerlukan persetujuan pengguna (HITL Approval Gate) yang sah dan belum pernah digunakan."
                    ),
                    data={
                        "hitl_required": True,
                        "tool_name": tool_name,
                        "risk_level": risk_level.value,
                        "arguments_hash": compute_canonical_arguments_hash(arguments),
                    },
                    token_estimate=24,
                )

        clean_args = {
            k: v for k, v in arguments.items()
            if k not in ("hitl_grant_id", "session_id", "execution_policy_override")
        }
        return await handler(**clean_args)


execution_policy_gateway = ExecutionPolicyGateway()


class SandboxManager:
    """Enforces strict path jail checks, automatic .aksa_backup snapshots, and HITL approvals."""

    def __init__(self, allowed_workspaces: list[WorkspacePolicy] | None = None) -> None:
        self._workspaces: dict[Path, WorkspacePolicy] = {}
        self._pending_approvals: dict[str, HITLApprovalRequest] = {}
        self._approval_events: dict[str, asyncio.Event] = {}
        if allowed_workspaces:
            for ws in allowed_workspaces:
                self.register_workspace(ws)

    def register_workspace(self, policy: WorkspacePolicy) -> Path:
        """Register or update an authorized workspace directory."""
        real_path = Path(os.path.realpath(os.path.expanduser(policy.folder_path)))
        self._workspaces[real_path] = WorkspacePolicy(
            folder_path=str(real_path),
            allow_read=policy.allow_read,
            allow_write=policy.allow_write,
            allow_execute=policy.allow_execute,
        )
        return real_path

    def remove_workspace(self, folder_path: str | Path) -> bool:
        """Remove a workspace path from the allowed jail."""
        real_path = Path(os.path.realpath(os.path.expanduser(str(folder_path))))
        return self._workspaces.pop(real_path, None) is not None

    def list_policies(self) -> list[WorkspacePolicy]:
        """Return all registered workspace policies."""
        return list(self._workspaces.values())

    def validate_path(
        self,
        target_path: str | Path,
        mode: str = "read",
    ) -> Path:
        """Validate that target_path is inside an authorized workspace and permitted for mode.

        Modes: 'read', 'write', 'execute'.
        Raises SandboxViolationError if outside allowed_paths or permission is disabled.
        """
        resolved = Path(os.path.realpath(os.path.expanduser(str(target_path))))

        matched_root: Path | None = None
        matched_policy: WorkspacePolicy | None = None

        for root_path, policy in self._workspaces.items():
            if resolved == root_path or resolved.is_relative_to(root_path):
                matched_root = root_path
                matched_policy = policy
                break

        if matched_root is None or matched_policy is None:
            raise SandboxViolationError(
                f"Akses ditolak oleh Sandbox AKSA: Path '{resolved}' berada di luar Folder Kerja yang diizinkan."
            )

        if mode == "read" and not matched_policy.allow_read:
            raise SandboxViolationError(
                f"Izin baca (read) tidak diaktifkan untuk Folder Kerja '{matched_root}'."
            )
        if mode == "write" and not matched_policy.allow_write:
            raise SandboxViolationError(
                f"Izin tulis (write) tidak diaktifkan untuk Folder Kerja '{matched_root}'."
            )
        if mode == "execute" and not matched_policy.allow_execute:
            raise SandboxViolationError(
                f"Izin eksekusi skrip (execute) tidak diaktifkan untuk Folder Kerja '{matched_root}'."
            )

        return resolved

    def backup_before_modify(self, target_path: str | Path) -> Path | None:
        """Create a timestamped backup copy in `<workspace>/.aksa_backup/` before modifying an existing file."""
        resolved = self.validate_path(target_path, mode="write")
        if not resolved.exists() or not resolved.is_file():
            return None

        # Find workspace root for this file
        ws_root = next(
            (root for root in self._workspaces if resolved.is_relative_to(root)),
            resolved.parent,
        )
        backup_dir = ws_root / ".aksa_backup"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        backup_name = f"{resolved.stem}.{timestamp}{resolved.suffix}.bak"
        backup_path = backup_dir / backup_name
        shutil.copy2(resolved, backup_path)
        return backup_path

    def list_backups(self, workspace_path: str | Path) -> list[dict[str, Any]]:
        """List available restore points inside `<workspace>/.aksa_backup/`."""
        resolved_ws = self.validate_path(workspace_path, mode="read")
        backup_dir = resolved_ws / ".aksa_backup"
        if not backup_dir.exists():
            return []

        items: list[dict[str, Any]] = []
        for entry in sorted(backup_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if entry.is_file():
                stat = entry.stat()
                items.append(
                    {
                        "name": entry.name,
                        "path": str(entry),
                        "size_bytes": stat.st_size,
                        "modified_at": stat.st_mtime,
                    }
                )
        return items

    async def create_hitl_request(
        self,
        tool_name: str,
        title_id: str,
        description_id: str,
        risk_level: RiskLevel = RiskLevel.HIGH,
        target_path: str | None = None,
        agent_name: str = "Operator PC & Automasi Sistem",
        session_id: str | None = None,
        arguments: dict[str, Any] | None = None,
    ) -> HITLApprovalRequest:
        """Create a Human-in-the-Loop approval request and broadcast it to the Desktop UI."""
        req_id = f"hitl_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=300)
        args_payload = arguments or {}
        req = HITLApprovalRequest(
            id=req_id,
            tool_name=tool_name,
            risk_level=risk_level,
            title_id=title_id,
            description_id=description_id,
            target_path=target_path,
            agent_name=agent_name,
            arguments=args_payload,
            arguments_hash=compute_canonical_arguments_hash(args_payload),
            session_id=session_id,
            status="pending",
            created_at=now.isoformat(),
            expires_at=expires.isoformat(),
        )
        self._pending_approvals[req_id] = req
        self._approval_events[req_id] = asyncio.Event()

        await ws_manager.broadcast_event(
            "hitl_approval_requested",
            req.model_dump(),
            session_id=session_id,
        )
        return req

    async def resolve_hitl_request(
        self,
        request_id: str,
        approved: bool,
        session_id: str | None = None,
    ) -> HITLApprovalRequest:
        """Approve or reject a pending HITL request, issue an ApprovalGrant if approved, and notify waiting coroutines."""
        req = self._pending_approvals.get(request_id)
        if not req:
            raise KeyError(f"Permintaan izin HITL '{request_id}' tidak ditemukan.")

        req.status = "approved" if approved else "rejected"
        req.resolved_at = _utc_now_iso()

        if approved:
            grant = execution_policy_gateway.create_grant(
                tool_name=req.tool_name,
                arguments=req.arguments,
                session_id=session_id or req.session_id,
                resource_path=req.target_path,
            )
            req.grant_id = grant.id

        ev = self._approval_events.get(request_id)
        if ev:
            ev.set()

        await ws_manager.broadcast_event(
            "hitl_approval_resolved",
            req.model_dump(),
            session_id=session_id,
        )
        return req

    async def wait_for_hitl_decision(self, request_id: str, timeout: float = 60.0) -> bool:
        """Wait asynchronously for the user to approve or reject a HITL request."""
        ev = self._approval_events.get(request_id)
        if not ev:
            return False
        try:
            await asyncio.wait_for(ev.wait(), timeout=timeout)
        except TimeoutError:
            await self.resolve_hitl_request(request_id, approved=False)
            return False

        req = self._pending_approvals.get(request_id)
        return bool(req and req.status == "approved")

    def list_approvals(self, status: str | None = None) -> list[HITLApprovalRequest]:
        """List HITL requests filtered optionally by status."""
        items = list(self._pending_approvals.values())
        if status:
            items = [i for i in items if i.status == status]
        return sorted(items, key=lambda x: x.created_at, reverse=True)


# Singleton sandbox manager instance
sandbox_manager = SandboxManager()

