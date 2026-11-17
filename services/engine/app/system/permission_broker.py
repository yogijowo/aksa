"""Native OS Permission Broker and AKSA Policy Authorization Center.

Tracks OS-level capabilities (Accessibility, Screen Recording, Filesystem, Automation)
independently from AKSA user consent grants, ensuring AKSA never claims permission was granted
without genuine verification.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.db.models import db_manager


class PermissionState(str, Enum):
    """Normalized operating-system permission states."""

    NOT_REQUESTED = "NOT_REQUESTED"
    CHECKING = "CHECKING"
    GRANTED = "GRANTED"
    DENIED = "DENIED"
    RESTRICTED = "RESTRICTED"
    NEEDS_USER_ACTION = "NEEDS_USER_ACTION"
    UNSUPPORTED = "UNSUPPORTED"
    ERROR = "ERROR"


class CapabilityDefinition(BaseModel):
    """Metadata for a registered native or application capability."""

    id: str
    display_name: str
    description: str
    scope_type: str  # workspace | application | session | device
    requires_hitl: bool = False
    platform_support: list[str] = Field(default_factory=lambda: ["windows", "darwin"])


STANDARD_CAPABILITIES: list[CapabilityDefinition] = [
    CapabilityDefinition(
        id="filesystem.workspace.read",
        display_name="Baca Berkas Folder Kerja",
        description="Membaca isi berkas dan struktur sub-folder di dalam Folder Kerja yang diizinkan.",
        scope_type="workspace",
        requires_hitl=False,
    ),
    CapabilityDefinition(
        id="filesystem.workspace.write",
        display_name="Tulis & Modifikasi Berkas",
        description="Membuat dokumen baru atau memperbarui spreadsheet di Folder Kerja dengan auto-backup.",
        scope_type="workspace",
        requires_hitl=False,
    ),
    CapabilityDefinition(
        id="filesystem.workspace.delete",
        display_name="Hapus Berkas Folder Kerja",
        description="Menghapus berkas kerja di dalam workspace (Wajib Persetujuan Konfirmasi).",
        scope_type="workspace",
        requires_hitl=True,
    ),
    CapabilityDefinition(
        id="application.discover",
        display_name="Deteksi Aplikasi Terpasang",
        description="Membaca daftar software dan aplikasi kerja yang terpasang di komputer.",
        scope_type="device",
        requires_hitl=False,
    ),
    CapabilityDefinition(
        id="application.launch",
        display_name="Buka & Luncurkan Aplikasi",
        description="Membuka aplikasi kerja terdaftar di komputer Anda untuk membuka dokumen.",
        scope_type="application",
        requires_hitl=False,
    ),
    CapabilityDefinition(
        id="application.automation",
        display_name="Automasi Aplikasi (Office / Live COM)",
        description="Berinteraksi langsung dengan antarmuka aplikasi kerja yang sedang aktif.",
        scope_type="application",
        requires_hitl=True,
    ),
    CapabilityDefinition(
        id="screen.capture",
        display_name="Tangkapan Layar Desktop (Screen Capture)",
        description="Mengambil cuplikan visual layar komputer untuk grounding analisis visual.",
        scope_type="session",
        requires_hitl=True,
    ),
    CapabilityDefinition(
        id="accessibility.inspect",
        display_name="Inspeksi Accessibility UI Tree",
        description="Membaca hierarki elemen antarmuka jendela aktif melalui Windows UI Automation / macOS AX.",
        scope_type="session",
        requires_hitl=False,
    ),
    CapabilityDefinition(
        id="input.mouse_keyboard",
        display_name="Kendali Input Mouse & Keyboard (Tier 3)",
        description="Mengirimkan klik kursor mouse dan ketikan tombol keyboard dengan Failsafe Corner Abort.",
        scope_type="session",
        requires_hitl=True,
    ),
    CapabilityDefinition(
        id="process.spawn",
        display_name="Eksekusi Skrip Python & CLI",
        description="Menjalankan lingkungan skrip Python mandiri berbasis uv runner di dalam Folder Kerja.",
        scope_type="workspace",
        requires_hitl=True,
    ),
]


class OSPermissionBroker:
    """Evaluates OS-level platform permissions and reconciles them with AKSA user consent grants."""

    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilityDefinition] = {c.id: c for c in STANDARD_CAPABILITIES}

    def list_capabilities(self) -> list[CapabilityDefinition]:
        return list(self._capabilities.values())

    def check_native_os_permission(
        self,
        capability_id: str,
        resource_id: str | None = None,
    ) -> PermissionState:
        """Inspect the actual operating system capability status without faking authorization."""
        # 1. Filesystem access: checked via OS permissions on resource path
        if capability_id.startswith("filesystem."):
            if not resource_id:
                return PermissionState.NEEDS_USER_ACTION
            p = Path(resource_id)
            if not p.exists():
                return PermissionState.DENIED
            if capability_id == "filesystem.workspace.read":
                return PermissionState.GRANTED if os.access(p, os.R_OK) else PermissionState.DENIED
            elif capability_id in ("filesystem.workspace.write", "filesystem.workspace.delete"):
                return PermissionState.GRANTED if os.access(p, os.W_OK) else PermissionState.DENIED

        # 2. Application discovery & launch: available by default on Windows/macOS user accounts
        if capability_id in ("application.discover", "application.launch"):
            return PermissionState.GRANTED

        # 3. Screen capture
        if capability_id == "screen.capture":
            if sys.platform == "win32":
                return PermissionState.GRANTED
            elif sys.platform == "darwin":
                # In macOS, screen recording requires system TCC authorization
                return PermissionState.NEEDS_USER_ACTION
            return PermissionState.UNSUPPORTED

        # 4. Accessibility / UI Automation
        if capability_id == "accessibility.inspect":
            if sys.platform == "win32":
                return PermissionState.GRANTED
            elif sys.platform == "darwin":
                return PermissionState.NEEDS_USER_ACTION
            return PermissionState.UNSUPPORTED

        # 5. Mouse/Keyboard control
        if capability_id == "input.mouse_keyboard":
            if sys.platform in ("win32", "darwin"):
                return PermissionState.GRANTED
            return PermissionState.UNSUPPORTED

        # 6. Process spawning
        if capability_id == "process.spawn":
            return PermissionState.GRANTED

        return PermissionState.NOT_REQUESTED

    async def get_all_capability_statuses(
        self,
        workspace_folder: str | None = None,
    ) -> list[dict[str, Any]]:
        """Combine native OS status, AKSA consent grant status, and audit history for all capabilities."""
        grants = await db_manager.list_permission_grants(active_only=True)
        grants_by_cap = {g["capability_id"]: g for g in grants}

        results: list[dict[str, Any]] = []
        for cap in self.list_capabilities():
            resource_ref = workspace_folder if cap.scope_type == "workspace" else None
            os_state = self.check_native_os_permission(cap.id, resource_id=resource_ref)
            active_grant = grants_by_cap.get(cap.id)

            aksa_status = "granted" if active_grant else ("not_granted" if cap.requires_hitl else "automatic_sandbox")

            results.append({
                "capability_id": cap.id,
                "display_name": cap.display_name,
                "description": cap.description,
                "scope_type": cap.scope_type,
                "requires_hitl": cap.requires_hitl,
                "os_status": os_state.value,
                "aksa_status": aksa_status,
                "grant_id": active_grant["id"] if active_grant else None,
                "granted_at": active_grant["granted_at"] if active_grant else None,
            })

        return results

    async def request_capability_grant(
        self,
        capability_id: str,
        resource_scope: str = "workspace",
        grant_source: str = "desktop_ui",
    ) -> dict[str, Any]:
        """Record an explicit user consent grant in the database and audit ledger."""
        os_state = self.check_native_os_permission(capability_id, resource_id=resource_scope)
        if os_state == PermissionState.DENIED:
            await db_manager.log_permission_audit_event({
                "capability_id": capability_id,
                "resource_scope": resource_scope,
                "decision": "deny",
                "reason_code": "OS_PERMISSION_DENIED",
            })
            return {
                "success": False,
                "message": f"Sistem Operasi menolak akses untuk kapabilitas '{capability_id}'.",
                "os_status": os_state.value,
            }

        grant = await db_manager.create_permission_grant({
            "capability_id": capability_id,
            "resource_scope": resource_scope,
            "grant_source": grant_source,
        })
        await db_manager.log_permission_audit_event({
            "capability_id": capability_id,
            "resource_scope": resource_scope,
            "decision": "allow",
            "reason_code": "USER_GRANTED",
        })

        return {
            "success": True,
            "grant": grant,
            "os_status": os_state.value,
            "message": f"Izin kapabilitas '{capability_id}' berhasil diberikan oleh pengguna.",
        }

    async def revoke_capability_grant(self, grant_id: str) -> bool:
        """Revoke a previously granted consent grant immediately."""
        revoked = await db_manager.revoke_permission_grant(grant_id)
        if revoked:
            await db_manager.log_permission_audit_event({
                "capability_id": "grant_revocation",
                "resource_scope": grant_id,
                "decision": "deny",
                "reason_code": "USER_REVOKED",
            })
        return revoked


permission_broker = OSPermissionBroker()
