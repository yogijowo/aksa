"""Tier 3 Visual Computer Use Engine with Postcondition Verification & Failsafe Abort.

Enforces honest capability reporting (separating available vs implemented), target-window validation,
sensitive window shielding, destructive action gates, and postcondition verification (P1.2).
"""

from __future__ import annotations

import asyncio
import sys
from enum import Enum
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from app.core.sandbox import RiskLevel, sandbox_manager
from app.system.permission_broker import PermissionState, permission_broker
from app.tools.registry import ToolResult, tool_registry


class ComputerActionType(str, Enum):
    """Supported GUI mouse, keyboard, and accessibility action types (Section 9.2)."""

    GET_ACTIVE_WINDOW = "get_active_window"
    CAPTURE_SCREEN = "capture_screen"
    FIND_ELEMENT = "find_element"
    CLICK_ELEMENT = "click_element"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    MOVE = "move"
    TYPE_TEXT = "type_text"
    PRESS_KEY = "press_key"
    PRESS_HOTKEY = "press_hotkey"
    SCROLL = "scroll"
    LAUNCH_APPLICATION = "launch_application"


SENSITIVE_WINDOW_KEYWORDS = (
    "1password",
    "bitwarden",
    "keepass",
    "lastpass",
    "windows security",
    "credential manager",
    "keychain access",
    "password",
    "kata sandi",
    "uac",
    "terminal - sudo",
)

DESTRUCTIVE_HOTKEYS = (
    ("ctrl", "alt", "del"),
    ("alt", "f4"),
    ("cmd", "q"),
    ("cmd", "opt", "esc"),
)


class ComputerUseAdapter:
    """Base interface for platform-specific Computer Use & Accessibility adapters."""

    platform_name: str = "generic"

    def get_capabilities(self) -> dict[str, dict[str, bool]]:
        """Separate capability availability from actual implementation completeness (P1.2)."""
        return {
            "active_window_inspection": {"available": False, "implemented": False},
            "screen_capture": {"available": False, "implemented": False},
            "ui_automation_tree": {"available": False, "implemented": False},
            "native_input": {"available": False, "implemented": False},
        }

    def get_active_window(self) -> dict[str, Any] | None:
        return None

    def is_sensitive_window(self, window_title: str | None) -> bool:
        if not window_title:
            return False
        lower = window_title.lower()
        return any(kw in lower for kw in SENSITIVE_WINDOW_KEYWORDS)

    def verify_postcondition(
        self,
        expected: dict[str, Any] | None,
        initial_state: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """Verify that UI state after action reflects the expected outcome."""
        if not expected:
            return False, "Tidak ada kriteria postcondition yang ditentukan (submitted_unverified)."

        current_win = self.get_active_window()
        current_title = (current_win.get("title") or "") if current_win else ""

        # 1. Expected window title contains
        if "window_title_contains" in expected:
            needle = expected["window_title_contains"].lower()
            if needle in current_title.lower():
                return True, f"Jendela aktif '{current_title}' sesuai dengan kriteria '{needle}'."
            return False, f"Jendela aktif '{current_title}' tidak memuat '{needle}'."

        # 2. Expected window closed
        if expected.get("window_closed") and initial_state:
            initial_hwnd = initial_state.get("hwnd")
            current_hwnd = current_win.get("hwnd") if current_win else None
            if current_hwnd != initial_hwnd:
                return True, "Jendela sebelumnya telah ditutup/berpindah fokus."
            return False, "Jendela target masih aktif dan belum tertutup."

        # 3. Expected active window match
        if "active_window_matches" in expected:
            target = expected["active_window_matches"]
            if current_title.strip() == target.strip():
                return True, f"Jendela aktif persis cocok dengan '{target}'."
            return False, f"Jendela aktif '{current_title}' tidak cocok dengan '{target}'."

        return False, "Postcondition tidak dapat diverifikasi secara otomatis pada adapter ini."


class WindowsComputerUseAdapter(ComputerUseAdapter):
    """Windows Computer Use adapter using Win32 foreground inspection and GDI."""

    platform_name: str = "windows"

    def get_capabilities(self) -> dict[str, dict[str, bool]]:
        is_win = sys.platform == "win32"
        return {
            "active_window_inspection": {"available": is_win, "implemented": True},
            "screen_capture": {"available": is_win, "implemented": True},
            "ui_automation_tree": {"available": is_win, "implemented": False},  # Win32 title only
            "native_input": {"available": is_win, "implemented": True},
        }

    def get_active_window(self) -> dict[str, Any] | None:
        if sys.platform != "win32":
            return None
        try:
            import ctypes

            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if hwnd:
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    if title:
                        is_sens = self.is_sensitive_window(title)
                        return {
                            "role": "window",
                            "hwnd": int(hwnd),
                            "title": "[REDACTED_SENSITIVE_WINDOW]" if is_sens else title,
                            "is_sensitive": is_sens,
                        }
        except Exception:
            pass
        return None


class MacOSComputerUseAdapter(ComputerUseAdapter):
    """macOS Computer Use adapter using CoreGraphics window information."""

    platform_name: str = "macos"

    def get_capabilities(self) -> dict[str, dict[str, bool]]:
        is_mac = sys.platform == "darwin"
        return {
            "active_window_inspection": {"available": is_mac, "implemented": True},
            "screen_capture": {"available": is_mac, "implemented": True},
            "ui_automation_tree": {"available": is_mac, "implemented": False},  # Requires AX trust
            "native_input": {"available": is_mac, "implemented": True},
        }

    def get_active_window(self) -> dict[str, Any] | None:
        if sys.platform != "darwin":
            return None
        try:
            # Check frontmost application via CoreGraphics or System Events
            import subprocess

            cmd = [
                "/usr/bin/osascript",
                "-e",
                'tell application "System Events" to get name of first application process whose frontmost is true',
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1.5)
            if proc.returncode == 0:
                title = proc.stdout.strip()
                if title:
                    is_sens = self.is_sensitive_window(title)
                    return {
                        "role": "application",
                        "title": "[REDACTED_SENSITIVE_WINDOW]" if is_sens else title,
                        "is_sensitive": is_sens,
                    }
        except Exception:
            pass
        return None


def get_platform_computer_use_adapter() -> ComputerUseAdapter:
    if sys.platform == "win32":
        return WindowsComputerUseAdapter()
    elif sys.platform == "darwin":
        return MacOSComputerUseAdapter()
    return ComputerUseAdapter()


class ComputerUseController:
    """Manages screen capture, Accessibility Tree grounding, and GUI actions with postcondition verification."""

    def __init__(self) -> None:
        self.failsafe_enabled: bool = True
        self.emergency_stop_active: bool = False
        self.screen_width: int = 1920
        self.screen_height: int = 1080
        self.emergency_hotkey: str = "Ctrl+Shift+Q"
        self.adapter: ComputerUseAdapter = get_platform_computer_use_adapter()

    def trigger_emergency_stop(self) -> dict[str, Any]:
        """Immediately halt all Tier 3 GUI mouse/keyboard operations."""
        self.emergency_stop_active = True
        return {
            "emergency_stop_active": True,
            "message": "Kontrol layar Tier 3 dihentikan seketika (Emergency Stop Aktif).",
        }

    def reset_emergency_stop(self) -> dict[str, Any]:
        """Re-enable Tier 3 GUI operations after user confirmation."""
        self.emergency_stop_active = False
        return {
            "emergency_stop_active": False,
            "message": "Kontrol layar Tier 3 diaktifkan kembali.",
        }

    def _check_failsafe_coordinates(self, x: int, y: int) -> None:
        """Abort immediately if target coordinates are in any of the 4 screen corners (0,0 etc.)."""
        if not self.failsafe_enabled:
            return
        margin = 5
        in_left = x <= margin
        in_right = x >= (self.screen_width - margin)
        in_top = y <= margin
        in_bottom = y >= (self.screen_height - margin)
        if (in_left and in_top) or (in_right and in_top) or (in_left and in_bottom) or (in_right and in_bottom):
            self.emergency_stop_active = True
            raise RuntimeError(
                f"Failsafe Corner Abort terpicu pada koordinat ({x}, {y})! Otomasi GUI dihentikan demi keamanan."
            )

    def _sync_capture_screen_and_a11y(self, workspace_path: str) -> ToolResult:
        if self.emergency_stop_active:
            return ToolResult(
                success=False,
                summary="Operasi dibatalkan: Tombol Darurat (Ctrl+Shift+Q / Failsafe) sedang aktif.",
                token_estimate=18,
            )

        resolved_ws = sandbox_manager.validate_path(workspace_path, mode="write")
        screenshots_dir = resolved_ws / ".aksa_screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        out_file = screenshots_dir / "screen_grid_latest.png"

        captured_via = "simulated_grid_canvas"
        is_live = False
        img: Image.Image | None = None

        try:
            import mss  # type: ignore[import-not-found]

            with mss.mss() as sct:
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                captured_via = "mss_live"
                is_live = True
        except Exception:
            try:
                from PIL import ImageGrab

                grabbed = ImageGrab.grab()
                if grabbed:
                    img = grabbed
                    captured_via = "imagegrab_live"
                    is_live = True
            except Exception:
                pass

        if img is None:
            img = Image.new("RGB", (1280, 720), color=(15, 17, 26))
            draw = ImageDraw.Draw(img)
            for gx in range(0, 1280, 160):
                draw.line([(gx, 0), (gx, 720)], fill=(40, 46, 68), width=1)
            for gy in range(0, 720, 120):
                draw.line([(0, gy), (1280, gy)], fill=(40, 46, 68), width=1)

        img.save(out_file)

        a11y_elements: list[dict[str, Any]] = []
        active_win = self.adapter.get_active_window()
        if active_win and not active_win.get("is_sensitive"):
            a11y_elements.append({
                "role": active_win.get("role", "window"),
                "title": active_win.get("title", ""),
                "bounds": [0, 0, img.width, img.height],
            })

        status_label = "nyata (Live)" if is_live else "simulasi (Headless Grid)"
        summary = (
            f"Tangkapan layar {status_label} ({img.width}x{img.height}, {captured_via}) "
            f"& {len(a11y_elements)} jendela aktif terdeteksi."
        )
        return ToolResult(
            success=True,
            summary=summary,
            data={
                "screenshot_path": str(out_file),
                "resolution": [img.width, img.height],
                "captured_via": captured_via,
                "is_live": is_live,
                "platform": sys.platform,
                "capabilities": self.adapter.get_capabilities(),
                "a11y_elements": a11y_elements,
            },
            artifacts=[str(out_file)],
            token_estimate=48,
        )

    async def capture_screen_and_a11y(self, workspace_path: str) -> ToolResult:
        """Capture screen with coordinate grid and inspect OS Accessibility Tree elements."""
        return await asyncio.to_thread(self._sync_capture_screen_and_a11y, workspace_path)

    async def visual_screen_action(
        self,
        action_type: str,
        x: int = 200,
        y: int = 200,
        text: str | None = None,
        hotkey: list[str] | None = None,
        button: str = "left",
        target_window_title: str | None = None,
        expected_postcondition: dict[str, Any] | None = None,
        timeout_seconds: float = 5.0,
    ) -> ToolResult:
        """Execute a Vision-grounded GUI action with target validation and verified postcondition (P1.2)."""
        valid_actions = {a.value for a in ComputerActionType}
        if action_type not in valid_actions:
            return ToolResult(
                success=False,
                summary=f"Aksi GUI '{action_type}' tidak didukung oleh sistem. Pilihan valid: {sorted(valid_actions)}.",
                data={
                    "status": "unsupported",
                    "action_type": action_type,
                    "supported_actions": sorted(valid_actions),
                    "precondition_verified": False,
                    "postcondition_verified": False,
                },
                token_estimate=16,
            )

        if self.emergency_stop_active:
            return ToolResult(
                success=False,
                summary="Operasi GUI ditolak karena Emergency Stop (Ctrl+Shift+Q) sedang aktif.",
                data={
                    "status": "rejected_emergency_stop",
                    "action_type": action_type,
                    "precondition_verified": False,
                    "postcondition_verified": False,
                },
                token_estimate=18,
            )

        # Inspect initial active window
        initial_win = self.adapter.get_active_window()
        initial_title = (initial_win.get("title") or "") if initial_win else ""

        # 1. Sensitive window shielding (Priority check: immediately block passwords/credential managers)
        if self.adapter.is_sensitive_window(target_window_title) or (
            initial_win and initial_win.get("is_sensitive")
        ):
            return ToolResult(
                success=False,
                summary="Operasi GUI diblokir demi keamanan: Jendela target terdeteksi sebagai dialog kredensial atau pengelola kata sandi.",
                data={
                    "status": "blocked_sensitive_window",
                    "action_type": action_type,
                    "precondition_verified": False,
                    "postcondition_verified": False,
                },
                token_estimate=20,
            )

        # 2. Target window validation: inspect initial active window
        if target_window_title and initial_win:
            if target_window_title.lower() not in initial_title.lower():
                return ToolResult(
                    success=False,
                    summary=(
                        f"Validasi Jendela Gagal: Jendela aktif saat ini adalah '{initial_title}', "
                        f"bukan jendela target '{target_window_title}'."
                    ),
                    data={
                        "status": "target_window_mismatch",
                        "expected_target": target_window_title,
                        "actual_active": initial_title,
                        "precondition_verified": False,
                        "postcondition_verified": False,
                    },
                    token_estimate=20,
                )

        # 3. Check for destructive hotkey combinations
        if action_type == "press_hotkey" and hotkey:
            norm_hk = tuple(k.lower() for k in hotkey)
            if any(all(k in norm_hk for k in dest) for dest in DESTRUCTIVE_HOTKEYS):
                return ToolResult(
                    success=False,
                    summary=f"Kombinasi hotkey destruktif {hotkey} diblokir. Memerlukan konfirmasi persetujuan pengguna (HITL).",
                    data={
                        "status": "destructive_action_blocked",
                        "hotkey": hotkey,
                        "precondition_verified": False,
                        "postcondition_verified": False,
                    },
                    token_estimate=20,
                )

        if action_type == "get_active_window":
            return ToolResult(
                success=initial_win is not None,
                summary="Berhasil memeriksa jendela aktif melalui adapter platform." if initial_win else "Tidak ada jendela aktif yang terdeteksi.",
                data={
                    "status": "executed" if initial_win else "unsupported",
                    "action_type": action_type,
                    "active_window": initial_win,
                    "adapter": self.adapter.platform_name,
                    "capabilities": self.adapter.get_capabilities(),
                    "precondition_verified": True,
                    "postcondition_verified": initial_win is not None,
                },
                token_estimate=22,
            )

        if action_type in ("click", "double_click", "move", "click_element"):
            self._check_failsafe_coordinates(x, y)

        executed_driver = "none"
        action_executed = False
        action_error: str | None = None

        try:
            import pyautogui  # type: ignore[import-not-found]

            pyautogui.FAILSAFE = True
            executed_driver = "pyautogui"

            if action_type in ("click", "click_element"):
                pyautogui.click(x=x, y=y, button=button)
            elif action_type == "double_click":
                pyautogui.doubleClick(x=x, y=y, button=button)
            elif action_type == "move":
                pyautogui.moveTo(x=x, y=y)
            elif action_type == "type_text" and text:
                pyautogui.write(text, interval=0.02)
            elif action_type in ("press_hotkey", "press_key") and hotkey:
                pyautogui.hotkey(*hotkey)
            elif action_type == "scroll":
                pyautogui.scroll(y)
            action_executed = True
        except ImportError:
            executed_driver = "unsupported_missing_driver"
            action_error = "Driver 'pyautogui' belum terpasang di environment engine."
        except Exception as exc:
            executed_driver = "failed"
            action_error = str(exc)

        detail = (
            f"koordinat ({x}, {y}) tombol {button}"
            if action_type in ("click", "double_click", "move", "click_element")
            else (f"teks '{text}'" if action_type == "type_text" else f"hotkey {hotkey}")
        )

        if not action_executed:
            summary = (
                f"Tier 3 Computer Use: Aksi '{action_type}' pada {detail} tidak dapat dieksekusi "
                f"({action_error or 'Mode Simulasi Tanpa Display Interaktif'})."
            )
            return ToolResult(
                success=False,
                summary=summary,
                data={
                    "status": "simulated",
                    "action_type": action_type,
                    "driver": executed_driver,
                    "adapter": self.adapter.platform_name,
                    "error": action_error,
                    "failsafe_enabled": self.failsafe_enabled,
                    "precondition_verified": True,
                    "postcondition_verified": False,
                },
                token_estimate=24,
            )

        # 4. Postcondition verification (P1.2)
        # Input was executed, now verify UI outcome:
        if expected_postcondition:
            post_ok, post_msg = self.adapter.verify_postcondition(expected_postcondition, initial_state=initial_win)
            if post_ok:
                summary = f"Tier 3 Computer Use ({executed_driver}): Aksi '{action_type}' berhasil dan postcondition terverifikasi: {post_msg}"
                return ToolResult(
                    success=True,
                    summary=summary,
                    data={
                        "status": "executed",
                        "action_type": action_type,
                        "driver": executed_driver,
                        "precondition_verified": True,
                        "postcondition_verified": True,
                        "postcondition_message": post_msg,
                    },
                    token_estimate=32,
                )
            else:
                summary = f"Tier 3 Computer Use ({executed_driver}): Input terkirim, namun postcondition gagal terbukti: {post_msg}"
                return ToolResult(
                    success=False,
                    summary=summary,
                    data={
                        "status": "postcondition_failed",
                        "action_type": action_type,
                        "driver": executed_driver,
                        "precondition_verified": True,
                        "postcondition_verified": False,
                        "postcondition_message": post_msg,
                    },
                    token_estimate=28,
                )

        # If no expected postcondition was provided, report honest status: submitted_unverified
        summary = (
            f"Tier 3 Computer Use ({executed_driver}): Aksi '{action_type}' pada {detail} telah dikirim ke OS, "
            "namun postcondition UI belum diverifikasi (submitted_unverified)."
        )
        return ToolResult(
            success=False,
            summary=summary,
            data={
                "status": "submitted_unverified",
                "action_type": action_type,
                "x": x,
                "y": y,
                "text": text,
                "hotkey": hotkey,
                "driver": executed_driver,
                "adapter": self.adapter.platform_name,
                "failsafe_enabled": self.failsafe_enabled,
                "precondition_verified": True,
                "postcondition_verified": False,
            },
            token_estimate=28,
        )


computer_use_controller = ComputerUseController()


def register_computer_use_tools() -> None:
    tool_registry.register(
        name="capture_screen_and_a11y",
        category="computer_use",
        description="Ambil tangkapan layar berpetak koordinat & daftar elemen Accessibility Tree.",
        handler=computer_use_controller.capture_screen_and_a11y,
        risk_level=RiskLevel.MEDIUM,
    )
    tool_registry.register(
        name="visual_screen_action",
        category="computer_use",
        description="Jalankan klik mouse, ketik teks, atau tombol pintas pada aplikasi desktop.",
        handler=computer_use_controller.visual_screen_action,
        risk_level=RiskLevel.HIGH,
    )


register_computer_use_tools()
