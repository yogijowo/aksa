"""Workspace Path Jail, Auto-Backup Manager, and Human-in-the-Loop (HITL) Approval Gate."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import stat
import threading
import urllib.parse
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.api.ws import ws_manager
from app.core.auth_context import get_default_host_principal


class RiskLevel(str, Enum):
    """Risk classification for tool operations (R0-R4 enterprise baseline + aliases)."""

    LOW = "low"                                   # R0/R1 alias: Read-only or safe workspace inspect
    MEDIUM = "medium"                             # R2 alias: Reversible write with auto-backup
    HIGH = "high"                                 # R3/R4 alias: High-risk / external / destructive
    R0_READ_LOW = "R0"
    R1_READ_SENSITIVE = "R1"
    R2_REVERSIBLE_WRITE = "R2"
    R3_EXTERNAL_SIDE_EFFECT = "R3"
    R4_DESTRUCTIVE_PRIVILEGED = "R4"


FORBIDDEN_POLICY_OVERRIDE_FIELDS = {
    "execution_policy_override",
    "skip_approval",
    "is_admin",
    "force_allow",
    "bypass_policy",
}


class WorkspacePolicy(BaseModel):
    """Permissions configured for an authorized workspace folder."""

    folder_path: str
    allow_read: bool = True
    allow_write: bool = True
    allow_execute: bool = False


class HITLApprovalRequest(BaseModel):
    """Represents a pending or resolved Human-in-the-Loop approval gate item."""

    id: str
    action_id: str = Field(default_factory=lambda: f"act_{uuid.uuid4().hex[:10]}")
    tool_name: str
    tool_version: str = "1.0.0"
    risk_level: RiskLevel
    title_id: str
    description_id: str
    target_path: str | None = None
    workspace_id: str | None = None
    agent_name: str = "Operator PC & Automasi Sistem"
    arguments: dict[str, Any] = Field(default_factory=dict)
    arguments_hash: str = ""
    session_id: str | None = None
    grant_id: str | None = None
    creator_principal_id: str = Field(default_factory=get_default_host_principal)
    resolver_principal_id: str | None = None
    status: str = "pending"  # pending | approved | rejected
    created_at: str
    expires_at: str | None = None
    resolved_at: str | None = None


class ApprovalGrant(BaseModel):
    """One-time cryptographic grant bound to exact action, tool, version, arguments, session, workspace, and resource."""

    id: str
    approval_id: str = ""
    action_id: str | None = None
    principal_id: str = Field(default_factory=get_default_host_principal)
    user_id: str = Field(default_factory=get_default_host_principal)
    tool_name: str
    tool_version: str = "1.0.0"
    arguments: dict[str, Any] = Field(default_factory=dict)
    arguments_hash: str
    session_id: str | None = None
    workspace_id: str | None = None
    resource_path: str | None = None
    resource_ids: list[str] = Field(default_factory=list)
    risk_level: str = "high"
    data_classification: str = "INTERNAL"
    requested_permissions: list[str] = Field(default_factory=list)
    created_at: str
    expires_at: str
    decided_at: str | None = None
    decision: str = "approved"
    one_time: bool = True
    policy_version: int = 1
    decision_reason: str | None = None
    consumed: bool = False


class SandboxViolationError(PermissionError):
    """Raised when a tool attempts to access a path outside authorized workspaces or lacks permission."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_canonical_arguments_hash(arguments: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 hash of tool arguments ignoring policy metadata."""
    filtered = {
        k: v
        for k, v in arguments.items()
        if k not in (
            "hitl_grant_id",
            "session_id",
            "workspace_id",
            "tool_version",
            "action_id",
            "principal_id",
            "resource_path",
        )
        and k not in FORBIDDEN_POLICY_OVERRIDE_FIELDS
    }
    cleaned = json.dumps(filtered, sort_keys=True, default=str)
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:32]


class ExecutionPolicyGateway:
    """Centralized policy gateway enforcing least privilege and verified, non-reusable HITL approvals."""

    def __init__(self) -> None:
        self._grants: dict[str, ApprovalGrant] = {}
        self._lock = threading.Lock()

    def create_grant(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: str | None = None,
        workspace_id: str | None = None,
        action_id: str | None = None,
        principal_id: str | None = None,
        resource_path: str | None = None,
        tool_version: str = "1.0.0",
        risk_level: str = "high",
        data_classification: str = "INTERNAL",
        ttl_seconds: int = 300,
    ) -> ApprovalGrant:
        grant_id = f"grant_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=ttl_seconds)
        now_iso = now.isoformat()
        eff_principal = principal_id or get_default_host_principal()
        filtered_args = {
            k: v
            for k, v in arguments.items()
            if k not in (
                "hitl_grant_id",
                "session_id",
                "workspace_id",
                "tool_version",
                "action_id",
                "principal_id",
                "resource_path",
            )
            and k not in FORBIDDEN_POLICY_OVERRIDE_FIELDS
        }
        canonical_res = (
            str(os.path.realpath(os.path.expanduser(str(resource_path))))
            if resource_path
            else None
        )
        grant = ApprovalGrant(
            id=grant_id,
            approval_id=grant_id,
            action_id=action_id,
            principal_id=eff_principal,
            user_id=eff_principal,
            tool_name=tool_name,
            tool_version=tool_version,
            arguments=filtered_args,
            arguments_hash=compute_canonical_arguments_hash(arguments),
            session_id=session_id,
            workspace_id=workspace_id,
            resource_path=canonical_res,
            resource_ids=[canonical_res] if canonical_res else [],
            risk_level=risk_level,
            data_classification=data_classification,
            created_at=now_iso,
            decided_at=now_iso,
            expires_at=expires.isoformat(),
            decision="approved",
            one_time=True,
            consumed=False,
        )
        with self._lock:
            self._grants[grant_id] = grant
        return grant

    def verify_and_consume_grant(
        self,
        grant_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: str | None = None,
        workspace_id: str | None = None,
        action_id: str | None = None,
        principal_id: str | None = None,
        resource_path: str | None = None,
        tool_version: str = "1.0.0",
    ) -> bool:
        if not grant_id or not str(grant_id).strip():
            return False

        with self._lock:
            grant = self._grants.get(grant_id)
            if not grant or grant.consumed:
                return False
            if grant.decision != "approved":
                return False

            now_iso = datetime.now(timezone.utc).isoformat()
            if now_iso > grant.expires_at:
                grant.decision = "expired"
                grant.consumed = True
                return False

            # Strict tool & version check
            if grant.tool_name != tool_name:
                return False
            if grant.tool_version != tool_version:
                return False

            # Arguments hash check
            if grant.arguments_hash != compute_canonical_arguments_hash(arguments):
                return False

            # Fail-closed session binding: if grant was bound to a session, action must match
            if grant.session_id:
                if not session_id or grant.session_id != session_id:
                    return False
            elif session_id:
                return False

            # Fail-closed workspace binding: if grant was bound to a workspace, action must match
            if grant.workspace_id:
                if not workspace_id or grant.workspace_id != workspace_id:
                    return False
            elif workspace_id:
                return False

            # Fail-closed action binding: if action_id is bound, must match strictly (P0-04)
            if grant.action_id:
                if not action_id or grant.action_id != action_id:
                    return False
            elif action_id:
                return False

            # Fail-closed principal binding
            if grant.principal_id:
                active_principal = principal_id or get_default_host_principal()
                if grant.principal_id != active_principal:
                    return False

            # Fail-closed resource path binding
            if grant.resource_path:
                if not resource_path:
                    return False
                canon_grant_res = os.path.realpath(os.path.expanduser(str(grant.resource_path)))
                canon_act_res = os.path.realpath(os.path.expanduser(str(resource_path)))
                if canon_grant_res != canon_act_res:
                    return False

            # Atomically consume one-time grant immediately before execution
            if grant.one_time:
                grant.consumed = True
            return True

    def revoke_grant(self, grant_id: str) -> bool:
        with self._lock:
            grant = self._grants.get(grant_id)
            if not grant:
                return False
            grant.decision = "revoked"
            grant.consumed = True
            return True

    def get_grant(self, grant_id: str) -> ApprovalGrant | None:
        with self._lock:
            return self._grants.get(grant_id)

    async def execute_tool(
        self,
        tool_name: str,
        handler: Callable[..., Awaitable[Any]],
        risk_level: RiskLevel,
        arguments: dict[str, Any],
        session_id: str | None = None,
    ) -> Any:
        """Evaluate policy before dispatching to underlying tool handler. Fail closed."""
        from app.tools.registry import ToolResult

        # 1. Actively reject any public request trying to pass policy override fields
        forbidden_found = FORBIDDEN_POLICY_OVERRIDE_FIELDS.intersection(arguments.keys())
        if forbidden_found:
            return ToolResult(
                success=False,
                summary=(
                    f"Pelanggaran Keamanan ExecutionPolicyGateway: Field ilegal {sorted(forbidden_found)} "
                    "ditolak secara eksplisit. Tidak ada bypass kebijakan yang diizinkan."
                ),
                data={
                    "policy_violation": "FORBIDDEN_OVERRIDE_FIELD",
                    "rejected_fields": sorted(forbidden_found),
                    "tool_name": tool_name,
                },
                token_estimate=20,
            )

        grant_id = arguments.get("hitl_grant_id")
        workspace_id = arguments.get("workspace_id")
        action_id = arguments.get("action_id")
        principal_id = arguments.get("principal_id") or get_default_host_principal()
        tool_version = arguments.get("tool_version", "1.0.0")
        resource_path = (
            arguments.get("resource_path")
            or arguments.get("target_path")
            or arguments.get("file_path")
            or arguments.get("working_dir")
        )

        requires_approval = risk_level in (
            RiskLevel.HIGH,
            RiskLevel.R3_EXTERNAL_SIDE_EFFECT,
            RiskLevel.R4_DESTRUCTIVE_PRIVILEGED,
        )

        if requires_approval:
            if not grant_id or not self.verify_and_consume_grant(
                grant_id=grant_id,
                tool_name=tool_name,
                arguments=arguments,
                session_id=session_id,
                workspace_id=workspace_id,
                action_id=action_id,
                principal_id=principal_id,
                resource_path=resource_path,
                tool_version=tool_version,
            ):
                return ToolResult(
                    success=False,
                    summary=(
                        f"Aksi berisiko tinggi '{tool_name}' dicegah oleh ExecutionPolicyGateway: "
                        "Memerlukan persetujuan pengguna (HITL Approval Gate) yang sah, terikat pada argumen, dan belum pernah digunakan."
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
            k: v
            for k, v in arguments.items()
            if k not in (
                "hitl_grant_id",
                "session_id",
                "workspace_id",
                "tool_version",
                "action_id",
                "principal_id",
            )
        }
        try:
            return await handler(**clean_args)
        except SandboxViolationError as sve:
            return ToolResult(
                success=False,
                summary=str(sve),
                data={"policy_violation": "SANDBOX_VIOLATION"},
                token_estimate=15,
            )
        except Exception as exc:
            if "Failsafe Corner Abort" in str(exc):
                raise
            return ToolResult(
                success=False,
                summary=f"Kesalahan eksekusi tool '{tool_name}': {exc}",
                data={"error": str(exc)},
                token_estimate=15,
            )


execution_policy_gateway = ExecutionPolicyGateway()


def canonicalize_and_validate_path(
    candidate_path: str | Path,
    authorized_root: str | Path,
) -> Path:
    """Canonicalize candidate_path and strictly verify that it resides within authorized_root.

    Rejects:
    - Path traversal sequences (../, ..\\)
    - URL-encoded traversals (%2e%2e, %2f, %5c)
    - Embedded null bytes
    - UNC network paths (\\\\, //)
    - Alternate Data Streams (ADS)
    - Symlinks / directory junctions resolving outside authorized_root
    - Special device files (FIFOs, sockets, character/block devices)

    Raises SandboxViolationError if the path attempts to escape authorized_root or is invalid.
    Never leaks whether a private non-authorized file exists on disk.
    """
    raw_str = str(candidate_path).strip()
    if "\0" in raw_str:
        raise SandboxViolationError("Akses ditolak oleh Sandbox AKSA: Path mengandung karakter null byte ilegal.")

    # URL-decode once and twice to handle %2e%2e and double-encoded traversals
    unquoted = urllib.parse.unquote(raw_str)
    unquoted_twice = urllib.parse.unquote(unquoted)
    for text in (raw_str, unquoted, unquoted_twice):
        if "\0" in text:
            raise SandboxViolationError("Akses ditolak oleh Sandbox AKSA: Path mengandung karakter null byte ilegal.")

    if unquoted_twice.startswith("\\\\") or unquoted_twice.startswith("//"):
        raise SandboxViolationError(
            f"Akses ditolak oleh Sandbox AKSA: Path jaringan UNC '{raw_str}' tidak diizinkan."
        )

    # Normalize Windows backslashes for cross-platform path traversal detection
    cleaned_path = unquoted_twice.replace("\\", "/")
    expanded = os.path.expanduser(cleaned_path)
    base_name = Path(expanded).name
    if ":" in base_name:
        raise SandboxViolationError(
            f"Akses ditolak oleh Sandbox AKSA: Alternate Data Stream (ADS) tidak diizinkan pada '{raw_str}'."
        )

    canonical_root = Path(os.path.realpath(os.path.expanduser(str(authorized_root))))

    # If candidate is relative, anchor it to authorized_root
    cand = Path(expanded)
    if not cand.is_absolute():
        cand = canonical_root / cand

    canonical_candidate = Path(os.path.realpath(cand))

    # Strict boundary check: candidate must be identical to root or a descendant of root
    if canonical_candidate != canonical_root and not canonical_candidate.is_relative_to(canonical_root):
        raise SandboxViolationError(
            "Akses ditolak oleh Sandbox AKSA: Path berada di luar Folder Kerja yang diizinkan."
        )

    # Special file check (FIFOs, sockets, devices)
    if canonical_candidate.exists():
        try:
            mode = canonical_candidate.stat().st_mode
            if stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode) or stat.S_ISCHR(mode) or stat.S_ISBLK(mode):
                raise SandboxViolationError(
                    "Akses ditolak oleh Sandbox AKSA: Tipe file khusus (FIFO/Socket/Device) tidak diizinkan."
                )
        except OSError:
            pass

    return canonical_candidate


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

    def clear_all_workspaces(self) -> int:
        """Revoke all registered workspace policies in memory immediately."""
        count = len(self._workspaces)
        self._workspaces.clear()
        return count

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
        Raises SandboxViolationError if outside allowed_paths, UNC network path, ADS, or permission is disabled.
        """
        raw_str = str(target_path).strip()
        if "\0" in raw_str:
            raise SandboxViolationError("Akses ditolak oleh Sandbox AKSA: Path mengandung karakter null byte ilegal.")

        unquoted = urllib.parse.unquote(raw_str)
        unquoted_twice = urllib.parse.unquote(unquoted)
        if "\0" in unquoted_twice:
            raise SandboxViolationError("Akses ditolak oleh Sandbox AKSA: Path mengandung karakter null byte ilegal.")

        if unquoted_twice.startswith("\\\\") or unquoted_twice.startswith("//"):
            raise SandboxViolationError(
                f"Akses ditolak oleh Sandbox AKSA: Path jaringan UNC '{raw_str}' tidak diizinkan."
            )

        expanded = os.path.expanduser(unquoted_twice)
        if ":" in Path(expanded).name:
            raise SandboxViolationError(
                f"Akses ditolak oleh Sandbox AKSA: Alternate Data Stream (ADS) tidak diizinkan pada '{raw_str}'."
            )

        resolved = Path(os.path.realpath(expanded))

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

        # Check for special files
        if resolved.exists():
            try:
                st_mode = resolved.stat().st_mode
                if stat.S_ISFIFO(st_mode) or stat.S_ISSOCK(st_mode) or stat.S_ISCHR(st_mode) or stat.S_ISBLK(st_mode):
                    raise SandboxViolationError(
                        "Akses ditolak oleh Sandbox AKSA: Tipe file khusus (FIFO/Socket/Device) tidak diizinkan."
                    )
            except OSError:
                pass

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
        action_id: str | None = None,
        session_id: str | None = None,
        workspace_id: str | None = None,
        arguments: dict[str, Any] | None = None,
        tool_version: str = "1.0.0",
        principal_id: str | None = None,
    ) -> HITLApprovalRequest:
        """Create a Human-in-the-Loop approval request and broadcast it to the Desktop UI."""
        req_id = f"hitl_{uuid.uuid4().hex[:10]}"
        act_id = action_id or f"act_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=300)
        args_payload = arguments or {}
        eff_principal = principal_id or get_default_host_principal()
        req = HITLApprovalRequest(
            id=req_id,
            action_id=act_id,
            tool_name=tool_name,
            tool_version=tool_version,
            risk_level=risk_level,
            title_id=title_id,
            description_id=description_id,
            target_path=target_path,
            workspace_id=workspace_id,
            agent_name=agent_name,
            arguments=args_payload,
            arguments_hash=compute_canonical_arguments_hash(args_payload),
            session_id=session_id,
            creator_principal_id=eff_principal,
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
        principal_id: str | None = None,
    ) -> HITLApprovalRequest:
        """Approve or reject a pending HITL request, issue an ApprovalGrant if approved, and notify waiting coroutines."""
        req = self._pending_approvals.get(request_id)
        if not req:
            raise KeyError(f"Permintaan izin HITL '{request_id}' tidak ditemukan.")

        eff_principal = principal_id or get_default_host_principal()
        req.status = "approved" if approved else "rejected"
        req.resolver_principal_id = eff_principal
        req.resolved_at = _utc_now_iso()

        if approved:
            grant = execution_policy_gateway.create_grant(
                tool_name=req.tool_name,
                tool_version=req.tool_version,
                arguments=req.arguments,
                session_id=session_id or req.session_id,
                workspace_id=req.workspace_id,
                action_id=req.action_id,
                principal_id=eff_principal,
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

    def list_approvals(
        self,
        status: str | None = None,
        principal_id: str | None = None,
    ) -> list[HITLApprovalRequest]:
        """List HITL requests filtered optionally by status and principal."""
        items = list(self._pending_approvals.values())
        if status:
            items = [i for i in items if i.status == status]
        if principal_id:
            items = [i for i in items if i.creator_principal_id == principal_id or not i.creator_principal_id]
        return sorted(items, key=lambda x: x.created_at, reverse=True)


# Singleton sandbox manager instance
sandbox_manager = SandboxManager()

