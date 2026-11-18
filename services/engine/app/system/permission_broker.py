"""Native OS Permission Broker and AKSA Policy Authorization Center.

Tracks OS-level capabilities (Accessibility, Screen Recording, Filesystem, Automation)
independently from AKSA user consent grants, ensuring AKSA never claims permission was granted
without genuine runtime OS verification (P0.4).
"""

from __future__ import annotations

import ctypes
import os
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from app.db.models import db_manager


class PermissionState(str, Enum):
    """Normalized operating-system permission states (Layer A - P0.4)."""

    UNSUPPORTED = "UNSUPPORTED"
    NOT_REQUESTED = "NOT_REQUESTED"
    NEEDS_USER_ACTION = "NEEDS_USER_ACTION"
    PENDING = "PENDING"
    GRANTED = "GRANTED"
    DENIED = "DENIED"
    REVOKED = "REVOKED"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"


class AKSAConsentState(str, Enum):
    """Normalized AKSA explicit user consent states (Layer B)."""

    NOT_GRANTED = "NOT_GRANTED"
    GRANTED_SCOPED = "GRANTED_SCOPED"
    DENIED = "DENIED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class CapabilityDefinition(BaseModel):
    """Metadata for a registered native or application capability."""

    id: str
    display_name: str
    description: str
    scope_type: str  # workspace | application | session | device
    requires_hitl: bool = False
    platform_support: list[str] = Field(default_factory=lambda: ["windows", "darwin", "linux"])
    revocation_guide: str = ""


STANDARD_CAPABILITIES: list[CapabilityDefinition] = [
    CapabilityDefinition(
        id="filesystem.workspace.read",
        display_name="Baca Berkas Folder Kerja",
        description="Membaca isi berkas dan struktur sub-folder di dalam Folder Kerja yang diizinkan.",
        scope_type="workspace",
        requires_hitl=False,
        revocation_guide="Hapus folder kerja dari daftar Folder Kerja di Pengaturan AKSA.",
    ),
    CapabilityDefinition(
        id="filesystem.workspace.write",
        display_name="Tulis & Modifikasi Berkas",
        description="Membuat dokumen baru atau memperbarui spreadsheet di Folder Kerja dengan auto-backup.",
        scope_type="workspace",
        requires_hitl=False,
        revocation_guide="Nonaktifkan izin tulis folder kerja pada daftar Folder Kerja di Pengaturan AKSA.",
    ),
    CapabilityDefinition(
        id="filesystem.workspace.delete",
        display_name="Hapus Berkas Folder Kerja",
        description="Menghapus berkas kerja di dalam workspace (Wajib Persetujuan Konfirmasi).",
        scope_type="workspace",
        requires_hitl=True,
        revocation_guide="Tolak dialog konfirmasi persetujuan saat agen meminta izin hapus berkas.",
    ),
    CapabilityDefinition(
        id="application.discover",
        display_name="Deteksi Aplikasi Terpasang",
        description="Membaca daftar software dan aplikasi kerja yang terpasang di komputer.",
        scope_type="device",
        requires_hitl=False,
        revocation_guide="Akses baca daftar aplikasi komputer dapat diputus melalui tab Izin & Akses PC.",
    ),
    CapabilityDefinition(
        id="application.launch",
        display_name="Buka & Luncurkan Aplikasi",
        description="Membuka aplikasi kerja terdaftar di komputer Anda untuk membuka dokumen.",
        scope_type="application",
        requires_hitl=False,
        revocation_guide="Putuskan otorisasi aplikasi tertentu di tab Aplikasi & Integrasi.",
    ),
    CapabilityDefinition(
        id="application.automation",
        display_name="Automasi Aplikasi (Office / Live COM)",
        description="Berinteraksi langsung dengan antarmuka aplikasi kerja yang sedang aktif.",
        scope_type="application",
        requires_hitl=True,
        revocation_guide="Putuskan akses pada tab Aplikasi & Integrasi atau tolak konfirmasi HITL.",
    ),
    CapabilityDefinition(
        id="screen.capture",
        display_name="Tangkapan Layar Desktop (Screen Capture)",
        description="Mengambil cuplikan visual layar komputer untuk grounding analisis visual.",
        scope_type="session",
        requires_hitl=True,
        revocation_guide="Cabut izin di Pengaturan Sistem > Privasi & Keamanan > Perekaman Layar (macOS) / Settings (Windows).",
    ),
    CapabilityDefinition(
        id="accessibility.inspect",
        display_name="Inspeksi Accessibility UI Tree",
        description="Membaca hierarki elemen antarmuka jendela aktif melalui Windows UI Automation / macOS AX.",
        scope_type="session",
        requires_hitl=False,
        revocation_guide="Cabut izin di Pengaturan Sistem > Privasi & Keamanan > Aksesibilitas (macOS).",
    ),
    CapabilityDefinition(
        id="input.mouse_keyboard",
        display_name="Kendali Input Mouse & Keyboard (Tier 3)",
        description="Mengirimkan klik kursor mouse dan ketikan tombol keyboard dengan Failsafe Corner Abort.",
        scope_type="session",
        requires_hitl=True,
        revocation_guide="Cabut izin Aksesibilitas di Pengaturan Sistem > Privasi & Keamanan > Aksesibilitas (macOS) atau Settings (Windows).",
    ),
    CapabilityDefinition(
        id="audio.microphone",
        display_name="Akses Mikrofon & Input Suara",
        description="Mendengarkan input audio pengguna untuk transkripsi dan perintah suara.",
        scope_type="session",
        requires_hitl=True,
        revocation_guide="Pengaturan Sistem > Privasi & Keamanan > Mikrofon (macOS) / Settings > Privacy & security > Microphone (Windows).",
    ),
    CapabilityDefinition(
        id="video.camera",
        display_name="Akses Kamera Video",
        description="Mengambil feed visual kamera untuk pemindaian berkas atau pengenalan dokumen.",
        scope_type="session",
        requires_hitl=True,
        revocation_guide="Pengaturan Sistem > Privasi & Keamanan > Kamera (macOS) / Settings > Privacy & security > Camera (Windows).",
    ),
    CapabilityDefinition(
        id="process.spawn",
        display_name="Eksekusi Skrip Python & CLI",
        description="Menjalankan lingkungan skrip Python mandiri berbasis uv runner di dalam Folder Kerja.",
        scope_type="workspace",
        requires_hitl=True,
        revocation_guide="Nonaktifkan runner Python atau tolak konfirmasi eksekusi skrip.",
    ),
]


def _check_macos_accessibility() -> PermissionState:
    """Verify macOS Accessibility trust via AXIsProcessTrusted."""
    try:
        from ctypes import util
        lib_name = util.find_library("ApplicationServices")
        if not lib_name:
            return PermissionState.NEEDS_USER_ACTION
        app_services = ctypes.cdll.LoadLibrary(lib_name)
        app_services.AXIsProcessTrusted.restype = ctypes.c_bool
        return PermissionState.GRANTED if bool(app_services.AXIsProcessTrusted()) else PermissionState.NEEDS_USER_ACTION
    except Exception:
        return PermissionState.ERROR


def _check_macos_screen_capture() -> PermissionState:
    """Verify macOS Screen Capture permission via CGPreflightScreenCaptureAccess."""
    try:
        from ctypes import util
        lib_name = util.find_library("CoreGraphics")
        if not lib_name:
            return PermissionState.NEEDS_USER_ACTION
        core_graphics = ctypes.cdll.LoadLibrary(lib_name)
        if hasattr(core_graphics, "CGPreflightScreenCaptureAccess"):
            core_graphics.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
            return PermissionState.GRANTED if bool(core_graphics.CGPreflightScreenCaptureAccess()) else PermissionState.NEEDS_USER_ACTION
        return PermissionState.NEEDS_USER_ACTION
    except Exception:
        return PermissionState.ERROR


def _check_macos_media_capture(media_type: str) -> PermissionState:
    """Verify macOS Camera / Microphone TCC permission via AVFoundation."""
    try:
        from ctypes import util
        objc = ctypes.cdll.LoadLibrary(util.find_library("objc"))
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.objc_msgSend.restype = ctypes.c_long
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

        ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AVFoundation.framework/AVFoundation")
        core_foundation = ctypes.cdll.LoadLibrary(util.find_library("CoreFoundation"))
        core_foundation.CFStringCreateWithCString.restype = ctypes.c_void_p
        core_foundation.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]

        kCFStringEncodingUTF8 = 0x08000100
        type_str = b"vide" if media_type == "video" else b"soun"
        cf_type = core_foundation.CFStringCreateWithCString(None, type_str, kCFStringEncodingUTF8)

        cls = objc.objc_getClass(b"AVCaptureDevice")
        sel = objc.sel_registerName(b"authorizationStatusForMediaType:")
        status = objc.objc_msgSend(cls, sel, cf_type)
        # 0 = NotDetermined, 1 = Restricted, 2 = Denied, 3 = Authorized
        if status == 3:
            return PermissionState.GRANTED
        elif status in (1, 2):
            return PermissionState.DENIED
        elif status == 0:
            return PermissionState.NEEDS_USER_ACTION
        return PermissionState.UNKNOWN
    except Exception:
        return PermissionState.UNKNOWN


def _check_windows_screen_capture() -> PermissionState:
    """Verify Windows screen capture capability.
    
    GetDC(0) alone does not prove permission under modern Windows privacy settings.
    Returns DENIED if desktop DC cannot be created, otherwise UNKNOWN unless verified.
    """
    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        hdc = user32.GetDC(0)
        if not hdc:
            return PermissionState.DENIED
        mem_dc = gdi32.CreateCompatibleDC(hdc)
        if not mem_dc:
            user32.ReleaseDC(0, hdc)
            return PermissionState.DENIED
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(0, hdc)
        # GDI device context works, but Windows Graphics Capture or privacy policy is not proven
        return PermissionState.UNKNOWN
    except Exception:
        return PermissionState.ERROR


def _check_windows_desktop_and_input() -> PermissionState:
    """Verify Windows desktop access and input injection capability.
    
    GetDesktopWindow() is open to all processes and does not prove SendInput / UIAutomation trust.
    """
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetDesktopWindow()
        if not hwnd or hwnd == 0:
            return PermissionState.DENIED
        if user32.GetSystemMetrics(0) <= 0:
            return PermissionState.DENIED
        # Basic desktop window exists, but UIPI / Accessibility capability cannot be confirmed blindly
        return PermissionState.UNKNOWN
    except Exception:
        return PermissionState.ERROR


def _check_linux_screen_and_input() -> PermissionState:
    """Detect Wayland vs X11 on Linux.
    
    DISPLAY alone does not prove input injection or screen recording capability.
    """
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session_type == "wayland":
        # Wayland security model requires explicit portal (xdg-desktop-portal)
        return PermissionState.NEEDS_USER_ACTION
    display = os.environ.get("DISPLAY")
    if not display:
        return PermissionState.DENIED
    # DISPLAY is present, but XTest and screen capture permissions are not proven
    return PermissionState.UNKNOWN


class OSPermissionBroker:
    """Evaluates OS-level platform permissions and reconciles them with AKSA user consent grants."""

    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilityDefinition] = {c.id: c for c in STANDARD_CAPABILITIES}
        # Allow test mock injectors for cross-platform simulation
        self._checker_overrides: dict[str, Callable[[], PermissionState]] = {}

    def list_capabilities(self) -> list[CapabilityDefinition]:
        return list(self._capabilities.values())

    def set_mock_checker(self, capability_id: str, checker: Callable[[], PermissionState] | None) -> None:
        """Inject a mock capability checker for cross-platform and edge case tests."""
        if checker is None:
            self._checker_overrides.pop(capability_id, None)
        else:
            self._checker_overrides[capability_id] = checker

    def clear_mock_checkers(self) -> None:
        """Reset all mock checkers."""
        self._checker_overrides.clear()

    def check_native_os_permission(
        self,
        capability_id: str,
        resource_id: str | None = None,
    ) -> PermissionState:
        """Inspect actual operating system capability status without inferring authorization from OS type (P0.4)."""
        # Check mock overrides first (used in testing platform-specific matrices)
        if capability_id in self._checker_overrides:
            return self._checker_overrides[capability_id]()

        # 1. Filesystem access: checked via OS permissions on resource path
        if capability_id.startswith("filesystem."):
            if not resource_id:
                return PermissionState.NOT_REQUESTED
            p = Path(resource_id)
            if not p.exists():
                return PermissionState.DENIED
            if capability_id == "filesystem.workspace.read":
                return PermissionState.GRANTED if os.access(p, os.R_OK) else PermissionState.DENIED
            elif capability_id in ("filesystem.workspace.write", "filesystem.workspace.delete"):
                return PermissionState.GRANTED if os.access(p, os.W_OK) else PermissionState.DENIED

        # 2. Application discovery & launch: check if execution environment permits discovering/launching
        if capability_id in ("application.discover", "application.launch"):
            if sys.platform in ("win32", "darwin"):
                return PermissionState.GRANTED
            elif sys.platform.startswith("linux"):
                return PermissionState.GRANTED if os.access("/bin/sh", os.X_OK) else PermissionState.DENIED
            return PermissionState.UNSUPPORTED

        # 3. Screen capture: verify through platform-specific API
        if capability_id == "screen.capture":
            if sys.platform == "darwin":
                return _check_macos_screen_capture()
            elif sys.platform == "win32":
                return _check_windows_screen_capture()
            elif sys.platform.startswith("linux"):
                return _check_linux_screen_and_input()
            return PermissionState.UNSUPPORTED

        # 4. Accessibility / UI Automation inspection: verify actual OS trust
        if capability_id == "accessibility.inspect":
            if sys.platform == "darwin":
                return _check_macos_accessibility()
            elif sys.platform == "win32":
                return _check_windows_desktop_and_input()
            elif sys.platform.startswith("linux"):
                return _check_linux_screen_and_input()
            return PermissionState.UNSUPPORTED

        # 5. Mouse/Keyboard synthetic input control: requires Accessibility trust on macOS
        if capability_id == "input.mouse_keyboard":
            if sys.platform == "darwin":
                return _check_macos_accessibility()
            elif sys.platform == "win32":
                return _check_windows_desktop_and_input()
            elif sys.platform.startswith("linux"):
                return _check_linux_screen_and_input()
            return PermissionState.UNSUPPORTED

        # 6. Live application automation (COM / AppleScript)
        # Note: CoInitialize on Windows or osascript binary presence on macOS does NOT prove application automation trust (P0-05)
        if capability_id == "application.automation":
            if sys.platform == "win32":
                return PermissionState.UNKNOWN
            elif sys.platform == "darwin":
                # AppleEvents requires explicit per-application TCC grant; presence of osascript binary is insufficient
                return PermissionState.NEEDS_USER_ACTION
            return PermissionState.UNSUPPORTED

        # 7. Audio & Video media capture
        if capability_id == "audio.microphone":
            if sys.platform == "darwin":
                return _check_macos_media_capture("audio")
            elif sys.platform in ("win32", "linux"):
                return PermissionState.UNKNOWN
            return PermissionState.UNSUPPORTED

        if capability_id == "video.camera":
            if sys.platform == "darwin":
                return _check_macos_media_capture("video")
            elif sys.platform in ("win32", "linux"):
                return PermissionState.UNKNOWN
            return PermissionState.UNSUPPORTED

        # 8. Process spawning
        if capability_id == "process.spawn":
            # Verify Python interpreter executable is runnable
            if os.access(sys.executable, os.X_OK):
                return PermissionState.GRANTED
            return PermissionState.DENIED

        return PermissionState.NOT_REQUESTED

    async def get_all_capability_statuses(
        self,
        workspace_folder: str | None = None,
    ) -> list[dict[str, Any]]:
        """Combine native OS status, AKSA consent grant status, and audit history for all capabilities."""
        all_grants = await db_manager.list_permission_grants(active_only=False)
        active_by_cap: dict[str, dict[str, Any]] = {}
        revoked_by_cap: dict[str, dict[str, Any]] = {}
        now_iso = datetime.now(timezone.utc).isoformat()

        for g in all_grants:
            cap_id = g["capability_id"]
            if g.get("revoked_at"):
                if cap_id not in revoked_by_cap:
                    revoked_by_cap[cap_id] = g
            elif g.get("expires_at") and g["expires_at"] < now_iso:
                continue
            else:
                if cap_id not in active_by_cap:
                    active_by_cap[cap_id] = g

        results: list[dict[str, Any]] = []
        for cap in self.list_capabilities():
            resource_ref = workspace_folder if cap.scope_type == "workspace" else None
            os_state = self.check_native_os_permission(cap.id, resource_id=resource_ref)
            active_grant = active_by_cap.get(cap.id)

            if active_grant:
                # If OS revoked permission, reflect that AKSA status is invalidated
                if os_state not in (PermissionState.GRANTED, PermissionState.NOT_REQUESTED):
                    aksa_status = "not_granted"
                    aksa_consent_state = AKSAConsentState.REVOKED.value
                else:
                    aksa_status = "granted"
                    aksa_consent_state = AKSAConsentState.GRANTED_SCOPED.value
            elif cap.id in revoked_by_cap:
                aksa_status = "not_granted"
                aksa_consent_state = AKSAConsentState.REVOKED.value
            else:
                aksa_status = "not_granted" if cap.requires_hitl else "automatic_sandbox"
                aksa_consent_state = AKSAConsentState.NOT_GRANTED.value

            results.append({
                "capability_id": cap.id,
                "display_name": cap.display_name,
                "description": cap.description,
                "scope_type": cap.scope_type,
                "requires_hitl": cap.requires_hitl,
                "os_status": os_state.value,
                "aksa_status": aksa_status,
                "aksa_consent_state": aksa_consent_state,
                "revocation_guide": cap.revocation_guide,
                "grant_id": active_grant["id"] if active_grant else None,
                "granted_at": active_grant["granted_at"] if active_grant else None,
            })

        return results

    async def has_active_consent(self, capability_id: str, resource_scope: str | None = None) -> bool:
        """Check whether explicit AKSA consent grant exists AND native OS permission is currently verified GRANTED."""
        # 1. Native OS permission re-check at runtime (P0.4)
        os_state = self.check_native_os_permission(capability_id, resource_id=resource_scope)
        if os_state != PermissionState.GRANTED:
            return False

        # 2. Layer B explicit consent grant check
        grants = await db_manager.list_permission_grants(active_only=True)
        now_iso = datetime.now(timezone.utc).isoformat()
        for g in grants:
            if g["capability_id"] != capability_id:
                continue
            if g.get("expires_at") and g["expires_at"] < now_iso:
                continue
            if resource_scope and g.get("resource_scope") not in (resource_scope, "workspace", "session", "device"):
                continue
            return True
        return False

    async def request_capability_grant(
        self,
        capability_id: str,
        resource_scope: str = "workspace",
        grant_source: str = "desktop_ui",
    ) -> dict[str, Any]:
        """Record an explicit user consent grant only after verifying native OS permission is not denied/needs action."""
        os_state = self.check_native_os_permission(capability_id, resource_id=resource_scope)
        if os_state != PermissionState.GRANTED:
            reason = f"OS_PERMISSION_{os_state.value}"
            await db_manager.log_permission_audit_event({
                "capability_id": capability_id,
                "resource_scope": resource_scope,
                "decision": "deny",
                "reason_code": reason,
            })
            if os_state == PermissionState.NEEDS_USER_ACTION:
                msg = (
                    f"Akses untuk kapabilitas '{capability_id}' memerlukan izin di Pengaturan Sistem Operasi "
                    "(Privacy & Security / TCC) sebelum dapat diaktifkan di AKSA."
                )
            elif os_state == PermissionState.DENIED:
                msg = f"Sistem Operasi menolak akses untuk kapabilitas '{capability_id}'."
            elif os_state == PermissionState.UNKNOWN:
                msg = f"Status izin Sistem Operasi belum dapat diverifikasi secara pasti ({os_state.value}). Pastikan izin aktif di Pengaturan Sistem Operasi."
            elif os_state == PermissionState.UNSUPPORTED:
                msg = f"Kapabilitas '{capability_id}' tidak didukung pada platform ini."
            else:
                msg = f"Status izin Sistem Operasi belum memenuhi syarat: {os_state.value}"

            return {
                "success": False,
                "message": msg,
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
