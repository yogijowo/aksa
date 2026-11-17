"""Agent Directory Service and Strict Isolation Policy for Per-Agent Storage Hierarchy."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings


class AgentIsolationError(PermissionError):
    """Raised when an agent attempts to access or mutate storage belonging to another agent."""


class AgentDirectoryService:
    """Manages the user-selected AKSA Root directory and provisions isolated per-agent folders."""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = (root_dir or settings.get_root_dir()).resolve()

    def set_root_dir(self, new_path: Path | str) -> dict[str, Any]:
        """Configure a new user-selected root directory with permission and space verification."""
        target = Path(new_path).expanduser().resolve()
        target.mkdir(parents=True, exist_ok=True)

        # Check write permissions
        test_file = target / ".aksa_write_test"
        try:
            test_file.write_text("test", encoding="utf-8")
            test_file.unlink(missing_ok=True)
        except Exception as exc:
            raise PermissionError(f"Root directory '{target}' tidak dapat ditulisi: {exc}") from exc

        # Check disk space
        stat = shutil.disk_usage(target)
        free_mb = stat.free // (1024 * 1024)

        self.root_dir = target
        settings.aksa_root_dir = target
        self.ensure_root_structure()

        return {
            "root_path": str(target),
            "free_space_mb": free_mb,
            "configured_at": datetime.now(timezone.utc).isoformat(),
            "status": "ready",
        }

    def ensure_root_structure(self) -> None:
        """Create standard master directory tree under AKSA root directory."""
        dirs_to_create = [
            self.root_dir / "system" / "registry",
            self.root_dir / "system" / "provider-cache",
            self.root_dir / "system" / "skill-catalog-cache",
            self.root_dir / "system" / "migrations",
            self.root_dir / "shared" / "skills",
            self.root_dir / "shared" / "templates",
            self.root_dir / "agents",
            self.root_dir / "workspaces",
            self.root_dir / "quarantine" / "skills",
            self.root_dir / "quarantine" / "mcp",
            self.root_dir / "quarantine" / "files",
            self.root_dir / "backups",
            self.root_dir / "exports",
        ]
        for d in dirs_to_create:
            d.mkdir(parents=True, exist_ok=True)

    def get_root_status(self) -> dict[str, Any]:
        """Return status, storage stats, and agent directory census."""
        self.ensure_root_structure()
        stat = shutil.disk_usage(self.root_dir)
        agents_dir = self.root_dir / "agents"
        agents_list = [p.name for p in agents_dir.iterdir() if p.is_dir()] if agents_dir.exists() else []

        return {
            "root_path": str(self.root_dir),
            "is_configured": True,
            "free_space_mb": stat.free // (1024 * 1024),
            "total_space_mb": stat.total // (1024 * 1024),
            "agents_count": len(agents_list),
            "agent_ids": agents_list,
        }

    def provision_agent_directory(
        self, agent_id: str, agent_metadata: dict[str, Any] | None = None
    ) -> Path:
        """Provision complete isolated folder hierarchy for an agent."""
        self.ensure_root_structure()
        safe_id = "".join(c for c in agent_id if c.isalnum() or c in ("-", "_")).strip()
        if not safe_id:
            safe_id = "agent-default"

        agent_dir = (self.root_dir / "agents" / safe_id).resolve()
        subdirs = [
            agent_dir / "memory" / "episodic",
            agent_dir / "memory" / "semantic",
            agent_dir / "memory" / "preferences",
            agent_dir / "memory" / "indexes",
            agent_dir / "skills" / "installed",
            agent_dir / "skills" / "learned",
            agent_dir / "skills" / "candidates",
            agent_dir / "skills" / "disabled",
            agent_dir / "skills" / "evaluations",
            agent_dir / "workflows",
            agent_dir / "knowledge",
            agent_dir / "projects",
            agent_dir / "artifacts",
            agent_dir / "evaluations",
            agent_dir / "state",
            agent_dir / "logs",
        ]
        for d in subdirs:
            d.mkdir(parents=True, exist_ok=True)

        # Write or update agent.json
        meta_file = agent_dir / "agent.json"
        if not meta_file.exists():
            payload = agent_metadata or {
                "id": safe_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "name": f"Agent {safe_id}",
                "role": "General Assistant",
            }
            meta_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        # Write initial PROFILE.md
        profile_file = agent_dir / "PROFILE.md"
        if not profile_file.exists():
            profile_content = (
                f"# Profil Agent: {safe_id}\n\n"
                f"- Dibuat: {datetime.now(timezone.utc).isoformat()}\n"
                f"- ID: `{safe_id}`\n"
                "- Status Pembelajaran: Aktif (Suggest only)\n"
                "- Lingkup Tugas: Bekerja dalam batas per-agent terisolasi.\n"
            )
            profile_file.write_text(profile_content, encoding="utf-8")

        return agent_dir

    def resolve_agent_path(self, agent_id: str, relative_path: str = "") -> Path:
        """Canonicalize path and ensure it stays strictly within the agent's folder."""
        safe_id = "".join(c for c in agent_id if c.isalnum() or c in ("-", "_")).strip()
        agent_dir = (self.root_dir / "agents" / safe_id).resolve()
        if not agent_dir.exists():
            agent_dir = self.provision_agent_directory(safe_id)

        target = (agent_dir / relative_path).resolve()
        try:
            target.relative_to(agent_dir)
        except ValueError as exc:
            raise AgentIsolationError(
                f"Path traversal terdeteksi: '{target}' berada di luar direktori agent '{safe_id}'"
            ) from exc

        return target


class AgentIsolationPolicy:
    """Enforces strict isolation between agent workspaces and memory layers."""

    def __init__(self, directory_service: AgentDirectoryService) -> None:
        self.directory_service = directory_service

    def validate_access(
        self,
        calling_agent_id: str,
        target_agent_id: str,
        relative_path: str = "",
        allow_shared: bool = True,
    ) -> Path:
        """Validate that calling agent has rights to access target path."""
        # Clean IDs
        caller = "".join(c for c in calling_agent_id if c.isalnum() or c in ("-", "_")).strip()
        target = "".join(c for c in target_agent_id if c.isalnum() or c in ("-", "_")).strip()

        # If accessing shared library
        if allow_shared and relative_path.startswith("shared/"):
            shared_path = (self.directory_service.root_dir / relative_path).resolve()
            shared_root = (self.directory_service.root_dir / "shared").resolve()
            try:
                shared_path.relative_to(shared_root)
                return shared_path
            except ValueError as exc:
                raise AgentIsolationError(f"Akses ke shared path ilegal: {relative_path}") from exc

        # Cross-agent isolation: an agent cannot access another agent's memory or private skills
        if caller != target and caller != "supervisor" and caller != "system":
            raise AgentIsolationError(
                f"Pelanggaran Isolasi Agent: Agent '{caller}' dilarang mengakses storage milik agent '{target}'."
            )

        return self.directory_service.resolve_agent_path(target, relative_path)

    def export_agent_package(self, agent_id: str) -> Path:
        """Export agent metadata, profile, memory, and learned skills into an export bundle."""
        safe_id = "".join(c for c in agent_id if c.isalnum() or c in ("-", "_")).strip()
        agent_dir = self.directory_service.resolve_agent_path(safe_id)
        export_dir = self.directory_service.root_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        zip_base = export_dir / f"{safe_id}_export_{timestamp}"
        archive_path = Path(shutil.make_archive(str(zip_base), "zip", root_dir=str(agent_dir)))
        return archive_path

    def purge_agent_data(self, agent_id: str) -> bool:
        """Permanently purge an agent's directory under user confirmation."""
        safe_id = "".join(c for c in agent_id if c.isalnum() or c in ("-", "_")).strip()
        agent_dir = (self.directory_service.root_dir / "agents" / safe_id).resolve()
        if agent_dir.exists():
            shutil.rmtree(agent_dir)
            return True
        return False


agent_directory_service = AgentDirectoryService()
agent_isolation_policy = AgentIsolationPolicy(agent_directory_service)
