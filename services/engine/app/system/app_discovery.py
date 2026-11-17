"""Installed and Running Application Discovery Engine (Windows & macOS).

Scans native operating system registries and application directories without requiring
administrator privileges or reading private user documents.
"""

from __future__ import annotations

import csv
import io
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.db.models import db_manager


class ApplicationRecord(BaseModel):
    """Normalized application inventory record (Section 5.1 Enterprise Spec)."""

    id: str
    app_id: str = ""
    platform: str = "windows"
    platform_app_id: str
    bundle_id: str | None = None
    aumid: str | None = None
    executable_path: str | None = None
    bundle_path: str | None = None
    display_name: str
    publisher: str | None = None
    version: str | None = None
    install_location: str | None = None
    install_scope: str = "machine"  # machine | user
    signature_status: str = "unknown"  # valid | invalid | unsigned | unknown
    install_source: str = "registry"  # registry | start_menu | package_manager | launch_services | application_directory | user_import
    detection_status: str = "installed"  # installed | running | portable | unavailable
    launch_status: str = "unknown"  # launchable | not_launchable | unknown
    automation_status: str = "unknown"  # supported | permission_required | unsupported | unknown
    confidence: float = 0.85
    detection_sources: list[str] = Field(default_factory=list)
    is_installed: bool = True
    is_running: bool = False
    is_connected: bool = False
    category_label: str = "Aplikasi Komputer Umum"
    available_adapters: list[str] = Field(default_factory=list)
    last_seen_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict)


def _sanitize_app_id(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", name.lower()).strip("_")
    return f"app_{cleaned[:32]}"


def classify_app_category(display_name: str, adapters: list[str]) -> str:
    """Categorize desktop application into user-friendly Indonesian domain categories."""
    name_lower = display_name.lower()
    if any(k in name_lower for k in ("excel", "word", "powerpoint", "powerpnt", "office", "libreoffice", "acrobat", "pdf")):
        return "Otomasi Dokumen Office"
    if any(k in name_lower for k in ("chrome", "firefox", "edge", "msedge", "brave", "opera", "safari", "browser")):
        return "Navigasi & Analisis Web"
    if any(k in name_lower for k in ("code", "visual studio", "sublime", "notepad", "cursor", "pycharm", "intellij", "git")):
        return "Penyunting Kode & Teks"
    if any(k in name_lower for k in ("telegram", "slack", "discord", "teams", "whatsapp", "zoom", "skype", "notion", "obsidian")):
        return "Komunikasi & Produktivitas"
    if any(k in name_lower for k in ("terminal", "powershell", "cmd", "explorer", "calculator", "kalkulator", "settings", "task manager")):
        return "Alat Sistem & Utilitas"
    if "office" in adapters:
        return "Otomasi Dokumen Office"
    if "browser" in adapters:
        return "Navigasi & Analisis Web"
    if "editor" in adapters:
        return "Penyunting Kode & Teks"
    return "Aplikasi Komputer Umum"


def _map_adapters(display_name: str, publisher: str | None) -> list[str]:
    name_lower = display_name.lower()
    adapters = ["launcher"]
    if any(k in name_lower for k in ("excel", "word", "powerpoint", "office", "libreoffice", "acrobat")):
        adapters.append("office")
        adapters.append("uia")
    elif any(k in name_lower for k in ("chrome", "firefox", "edge", "brave", "browser")):
        adapters.append("browser")
        adapters.append("uia")
    elif any(k in name_lower for k in ("visual studio code", "vscode", "sublime", "notepad", "cursor")):
        adapters.append("editor")
    return list(dict.fromkeys(adapters))


class ApplicationDiscoveryManager:
    """Discovers installed desktop software, inspects running status, and launches apps safely."""

    def __init__(self) -> None:
        self.cached_apps: dict[str, ApplicationRecord] = {}

    def get_running_process_names(self) -> set[str]:
        """Return lowercased executable names of currently running user processes."""
        running = set()
        if sys.platform == "win32":
            try:
                proc = subprocess.run(
                    ["tasklist", "/FO", "CSV", "/NH"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=3.0,
                )
                if proc.returncode == 0:
                    reader = csv.reader(io.StringIO(proc.stdout))
                    for row in reader:
                        if row:
                            running.add(row[0].strip().lower())
            except Exception:
                pass
        elif sys.platform == "darwin":
            try:
                proc = subprocess.run(
                    ["ps", "-eo", "comm="],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=3.0,
                )
                if proc.returncode == 0:
                    for line in proc.stdout.splitlines():
                        name = Path(line.strip()).name.lower()
                        if name:
                            running.add(name)
            except Exception:
                pass
        return running

    def scan_windows_installed_apps(self) -> list[ApplicationRecord]:
        """Scan Windows Registry Uninstall keys for 64-bit, 32-bit, and user-level apps."""
        if sys.platform != "win32":
            return []

        import winreg

        discovered: dict[str, ApplicationRecord] = {}
        running_procs = self.get_running_process_names()

        registry_targets = [
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", "machine"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall", "machine"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", "user"),
        ]

        for hkey, subkey_path, scope in registry_targets:
            try:
                with winreg.OpenKey(hkey, subkey_path) as parent_key:
                    num_subkeys = winreg.QueryInfoKey(parent_key)[0]
                    for idx in range(num_subkeys):
                        try:
                            key_name = winreg.EnumKey(parent_key, idx)
                            with winreg.OpenKey(parent_key, key_name) as subkey:
                                try:
                                    disp_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                except Exception:
                                    continue

                                if not disp_name or not str(disp_name).strip():
                                    continue

                                disp_name = str(disp_name).strip()
                                lower_disp = disp_name.lower()
                                # Ignore updates, language packs, redistributables, and driver packages
                                if any(disp_name.startswith(p) for p in ("KB", "Security Update", "Update for")) or any(
                                    p in lower_disp for p in ("redistributable", "windows driver package", "setup c++")
                                ):
                                    continue

                                version = None
                                try:
                                    v_val, _ = winreg.QueryValueEx(subkey, "DisplayVersion")
                                    version = str(v_val).strip()
                                except Exception:
                                    pass

                                publisher = None
                                try:
                                    p_val, _ = winreg.QueryValueEx(subkey, "Publisher")
                                    publisher = str(p_val).strip()
                                except Exception:
                                    pass

                                location = None
                                try:
                                    l_val, _ = winreg.QueryValueEx(subkey, "InstallLocation")
                                    raw_loc = str(l_val).strip().strip('"')
                                    if raw_loc:
                                        location = raw_loc
                                except Exception:
                                    pass

                                exe_path = None
                                try:
                                    icon_val, _ = winreg.QueryValueEx(subkey, "DisplayIcon")
                                    raw_icon = str(icon_val).split(",")[0].strip().strip('"')
                                    if raw_icon and raw_icon.lower().endswith(".exe") and Path(raw_icon).exists():
                                        exe_path = raw_icon
                                except Exception:
                                    pass

                                app_id = _sanitize_app_id(disp_name)
                                adapters = _map_adapters(disp_name, publisher)
                                category_label = classify_app_category(disp_name, adapters)

                                # Check if running
                                is_running = False
                                name_slug = re.sub(r"[^a-zA-Z0-9]+", "", disp_name.lower())
                                for proc in running_procs:
                                    if name_slug and (name_slug in proc or proc.startswith(name_slug[:6])):
                                        is_running = True
                                        break

                                has_valid_target = bool(
                                    (exe_path and Path(exe_path).exists())
                                    or (location and Path(location).exists())
                                )
                                launch_status = "launchable" if has_valid_target else "not_launchable"
                                automation_status = "supported" if ("office" in adapters or "uia" in adapters) else "permission_required"
                                confidence = 0.95 if has_valid_target else 0.75

                                if app_id not in discovered:
                                    discovered[app_id] = ApplicationRecord(
                                        id=app_id,
                                        app_id=app_id,
                                        platform="windows",
                                        platform_app_id=key_name,
                                        executable_path=exe_path,
                                        display_name=disp_name,
                                        publisher=publisher,
                                        version=version,
                                        install_location=exe_path or location,
                                        install_scope=scope,
                                        install_source="registry",
                                        detection_status="running" if is_running else "installed",
                                        launch_status=launch_status,
                                        automation_status=automation_status,
                                        confidence=confidence,
                                        detection_sources=["registry"],
                                        is_installed=True,
                                        is_running=is_running,
                                        category_label=category_label,
                                        available_adapters=adapters,
                                        metadata={
                                            "install_source": "registry",
                                            "launch_status": launch_status,
                                            "automation_status": automation_status,
                                            "confidence": confidence,
                                            "executable_path": exe_path,
                                        },
                                    )
                        except Exception:
                            continue
            except Exception:
                continue

        return list(discovered.values())

    def scan_macos_installed_apps(self) -> list[ApplicationRecord]:
        """Scan macOS /Applications and ~/Applications directories for standard .app bundles."""
        if sys.platform != "darwin":
            return []

        import plistlib

        discovered: dict[str, ApplicationRecord] = {}
        running_procs = self.get_running_process_names()
        app_dirs = [Path("/Applications"), Path("/System/Applications"), Path.home() / "Applications"]

        for base in app_dirs:
            if not base.exists() or not base.is_dir():
                continue
            for item in base.glob("*.app"):
                try:
                    plist_path = item / "Contents" / "Info.plist"
                    display_name = item.stem
                    bundle_id = None
                    version = None

                    if plist_path.exists():
                        with open(plist_path, "rb") as f:
                            plist_data = plistlib.load(f)
                            display_name = (
                                plist_data.get("CFBundleDisplayName")
                                or plist_data.get("CFBundleName")
                                or item.stem
                            )
                            bundle_id = plist_data.get("CFBundleIdentifier")
                            version = plist_data.get("CFBundleShortVersionString") or plist_data.get("CFBundleVersion")

                    app_id = _sanitize_app_id(display_name)
                    is_running = display_name.lower() in running_procs or item.stem.lower() in running_procs
                    adapters = _map_adapters(str(display_name), None)
                    category_label = classify_app_category(str(display_name), adapters)

                    discovered[app_id] = ApplicationRecord(
                        id=app_id,
                        app_id=app_id,
                        platform="darwin",
                        platform_app_id=bundle_id or item.name,
                        bundle_id=bundle_id,
                        bundle_path=str(item),
                        display_name=str(display_name),
                        publisher=None,
                        version=str(version) if version else None,
                        install_location=str(item),
                        install_scope="machine" if base.name == "Applications" else "user",
                        install_source="application_directory",
                        detection_status="running" if is_running else "installed",
                        launch_status="launchable",
                        automation_status="permission_required",
                        confidence=0.98,
                        detection_sources=["bundle"],
                        is_installed=True,
                        is_running=is_running,
                        category_label=category_label,
                        available_adapters=adapters,
                        metadata={
                            "install_source": "application_directory",
                            "launch_status": "launchable",
                            "automation_status": "permission_required",
                            "confidence": 0.98,
                            "bundle_path": str(item),
                        },
                    )
                except Exception:
                    continue

        return list(discovered.values())

    def scan_posix_installed_binaries(self) -> list[ApplicationRecord]:
        """Scan genuine installed binaries on POSIX/Linux environments without fake fallbacks."""
        import shutil

        discovered: list[ApplicationRecord] = []
        candidates = [
            ("python3", "Python 3 Runtime", "Penyunting Kode & Teks"),
            ("git", "Git Version Control", "Penyunting Kode & Teks"),
            ("bash", "GNU Bourne-Again Shell", "Alat Sistem & Utilitas"),
        ]
        for bin_name, label, cat in candidates:
            resolved = shutil.which(bin_name)
            if resolved and Path(resolved).exists():
                app_id = _sanitize_app_id(label)
                discovered.append(
                    ApplicationRecord(
                        id=app_id,
                        app_id=app_id,
                        platform=sys.platform,
                        platform_app_id=bin_name,
                        executable_path=resolved,
                        display_name=label,
                        publisher="System Package Manager",
                        install_location=resolved,
                        install_source="package_manager",
                        detection_status="installed",
                        launch_status="launchable",
                        automation_status="supported",
                        confidence=1.0,
                        detection_sources=["package_manager"],
                        is_installed=True,
                        is_running=False,
                        category_label=cat,
                        available_adapters=["launcher"],
                        metadata={
                            "install_source": "package_manager",
                            "launch_status": "launchable",
                            "confidence": 1.0,
                            "executable_path": resolved,
                        },
                    )
                )
        return discovered

    async def scan_and_sync(self) -> list[dict[str, Any]]:
        """Run platform scanner and synchronize genuine discovered records into SQLite database (no fake fallbacks)."""
        records: list[ApplicationRecord] = []
        if sys.platform == "win32":
            records = self.scan_windows_installed_apps()
        elif sys.platform == "darwin":
            records = self.scan_macos_installed_apps()
        else:
            records = self.scan_posix_installed_binaries()

        synced = []
        for r in records:
            self.cached_apps[r.id] = r
            db_item = await db_manager.upsert_installed_app(r.model_dump())
            synced.append(db_item)

        return synced

    async def launch_application(
        self,
        app_id: str,
        document_path: str | None = None,
    ) -> dict[str, Any]:
        """Safely launch an application ONLY after verifying executable/install path exists on disk."""
        app = await db_manager.get_installed_app(app_id)
        if not app:
            return {
                "success": False,
                "launch_status": "not_launchable",
                "message": f"Aplikasi '{app_id}' tidak ditemukan dalam katalog.",
            }

        target = document_path or app.get("install_location") or app.get("metadata", {}).get("executable_path")
        if not target or not str(target).strip():
            return {
                "success": False,
                "launch_status": "not_launchable",
                "message": f"Aplikasi '{app['display_name']}' tidak memiliki lokasi executable (InstallLocation kosong).",
            }

        target_path = Path(str(target).strip())
        if not target_path.exists():
            return {
                "success": False,
                "launch_status": "not_launchable",
                "message": f"Lokasi berkas aplikasi '{app['display_name']}' ({target_path}) tidak ditemukan di disk.",
            }

        try:
            if sys.platform == "win32":
                os.startfile(str(target_path))  # type: ignore[attr-defined]
                return {
                    "success": True,
                    "launch_status": "launchable",
                    "message": f"Berhasil membuka '{app['display_name']}' ({target_path}).",
                }
            elif sys.platform == "darwin":
                proc = subprocess.run(["open", str(target_path)], check=False, capture_output=True, text=True)
                if proc.returncode == 0:
                    return {
                        "success": True,
                        "launch_status": "launchable",
                        "message": f"Berhasil membuka aplikasi '{app['display_name']}' di macOS.",
                    }
                return {
                    "success": False,
                    "launch_status": "not_launchable",
                    "message": f"Gagal membuka aplikasi '{app['display_name']}': {proc.stderr.strip()}",
                }
            else:
                return {
                    "success": True,
                    "launch_status": "launchable",
                    "message": f"Path aplikasi '{app['display_name']}' ({target_path}) terverifikasi.",
                }
        except Exception as exc:
            return {
                "success": False,
                "launch_status": "not_launchable",
                "message": f"Gagal membuka aplikasi '{app['display_name']}': {exc}",
            }


application_discovery_manager = ApplicationDiscoveryManager()
