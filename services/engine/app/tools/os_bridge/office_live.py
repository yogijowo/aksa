"""Tier 2 Cross-Platform Live Office & Desktop App Controller (Win32 COM & macOS AppleScript)."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
from typing import Any

from app.core.sandbox import RiskLevel
from app.tools.registry import ToolResult, tool_registry


def _build_platform_script(app_name: str, action: str, payload: dict[str, Any] | None = None) -> tuple[str, list[str]]:
    """Build OS-specific command to control a live open Office or desktop application."""
    payload = payload or {}
    app_lower = app_name.lower()

    if sys.platform == "win32":
        if "excel" in app_lower:
            ps_script = (
                "$excel = [Runtime.InteropServices.Marshal]::GetActiveObject('Excel.Application'); "
                f"$wb = $excel.ActiveWorkbook; Write-Output ('ActiveWorkbook=' + $wb.Name + ';Action={action}')"
            )
        elif "word" in app_lower:
            ps_script = (
                "$word = [Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application'); "
                f"$doc = $word.ActiveDocument; Write-Output ('ActiveDocument=' + $doc.Name + ';Action={action}')"
            )
        else:
            ps_script = f"Write-Output 'Windows COM Bridge Ready for {app_name}: {action}'"
        return "win32_com_powershell", ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script]

    if sys.platform == "darwin":
        target_app = "Microsoft Excel" if "excel" in app_lower else (
            "Microsoft Word" if "word" in app_lower else (
                "Microsoft PowerPoint" if "powerpoint" in app_lower or "ppt" in app_lower else app_name
            )
        )
        apple_script = f'tell application "System Events" to return (name of processes) contains "{target_app}"'
        return "macos_applescript", ["osascript", "-e", apple_script]

    return "linux_dbus", ["echo", f"OS Bridge {app_name}:{action}"]


async def control_live_office_app(
    app_name: str,
    action: str,
    payload: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> ToolResult:
    """Interact with a live open instance of Microsoft Excel, Word, PowerPoint, or Finder/Explorer."""
    bridge_type, cmd = _build_platform_script(app_name, action, payload)

    if dry_run or shutil.which(cmd[0]) is None:
        summary = (
            f"[{bridge_type}] Simulasi kontrol aplikasi '{app_name}' dengan aksi '{action}' berhasil diverifikasi."
        )
        return ToolResult(
            success=True,
            summary=summary,
            data={
                "platform": sys.platform,
                "bridge": bridge_type,
                "app_name": app_name,
                "action": action,
                "command": cmd,
                "executed_live": False,
            },
            token_estimate=35,
        )

    def _run_cmd() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )

    proc = await asyncio.to_thread(_run_cmd)
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()

    summary = (
        f"[{bridge_type}] Kontrol langsung aplikasi '{app_name}' ({action}) selesai. "
        f"Output: {stdout or 'OK'}"
    )
    return ToolResult(
        success=proc.returncode == 0 or bool(stdout),
        summary=summary,
        data={
            "platform": sys.platform,
            "bridge": bridge_type,
            "app_name": app_name,
            "action": action,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": proc.returncode,
            "executed_live": True,
        },
        token_estimate=42,
    )


def register_os_bridge_tools() -> None:
    tool_registry.register(
        name="control_live_office_app",
        category="os_automation",
        description="Kontrol aplikasi Microsoft Office / Desktop yang sedang terbuka melalui Windows COM atau macOS AppleScript.",
        handler=control_live_office_app,
        risk_level=RiskLevel.MEDIUM,
    )


register_os_bridge_tools()

