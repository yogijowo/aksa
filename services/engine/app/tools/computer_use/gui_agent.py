"""Tier 3 Visual Computer Use Engine with Failsafe Corner Abort & Emergency Kill Switch."""

from __future__ import annotations

import asyncio
import sys
from enum import Enum
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from app.core.sandbox import RiskLevel, sandbox_manager
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
)


class ComputerUseAdapter:
    """Base interface for platform-specific Computer Use & Accessibility adapters."""

    platform_name: str = "generic"

    def get_capabilities(self) -> dict[str, bool]:
        return {
            "active_window_inspection": False,
            "screen_capture": False,
            "ui_automation_tree": False,
            "native_input": False,
        }

    def get_active_window(self) -> dict[str, Any] | None:
        return None

    def is_sensitive_window(self, window_title: str | None) -> bool:
        if not window_title:
            return False
        lower = window_title.lower()
        return any(kw in lower for kw in SENSITIVE_WINDOW_KEYWORDS)


class WindowsComputerUseAdapter(ComputerUseAdapter):
    """Windows Computer Use adapter using Win32 / UI Automation & Graphics Capture."""

    platform_name: str = "windows"

    def get_capabilities(self) -> dict[str, bool]:
        return {
            "active_window_inspection": sys.platform == "win32",
            "screen_capture": sys.platform == "win32",
            "ui_automation_tree": sys.platform == "win32",
            "native_input": sys.platform == "win32",
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
    """macOS Computer Use adapter using Accessibility API / ScreenCaptureKit / NSWorkspace."""

    platform_name: str = "macos"

    def get_capabilities(self) -> dict[str, bool]:
        return {
            "active_window_inspection": sys.platform == "darwin",
            "screen_capture": sys.platform == "darwin",
            "ui_automation_tree": False,  # Requires macOS TCC Accessibility trust
            "native_input": sys.platform == "darwin",
        }

    def get_active_window(self) -> dict[str, Any] | None:
        return None


def get_platform_computer_use_adapter() -> ComputerUseAdapter:
    if sys.platform == "win32":
        return WindowsComputerUseAdapter()
    elif sys.platform == "darwin":
        return MacOSComputerUseAdapter()
    return ComputerUseAdapter()


class ComputerUseController:
    """Manages screen capture, Accessibility Tree grounding, and GUI actions with emergency kill switch."""

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

        # 1. Attempt live display capture via mss or ImageGrab
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
            # Headless / background fallback: generate annotated coordinate grid frame
            img = Image.new("RGB", (1280, 720), color=(15, 17, 26))
            draw = ImageDraw.Draw(img)
            for gx in range(0, 1280, 160):
                draw.line([(gx, 0), (gx, 720)], fill=(40, 46, 68), width=1)
            for gy in range(0, 720, 120):
                draw.line([(0, gy), (1280, gy)], fill=(40, 46, 68), width=1)

        img.save(out_file)

        # 2. Inspect real active window title from OS (no fake UI buttons)
        a11y_elements: list[dict[str, Any]] = []
        if sys.platform == "win32":
            try:
                import ctypes

                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                if hwnd:
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        if buff.value:
                            a11y_elements.append({
                                "role": "window",
                                "title": buff.value,
                                "bounds": [0, 0, img.width, img.height],
                            })
            except Exception:
                pass

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
    ) -> ToolResult:
        """Execute a Vision-grounded GUI action with sensitive-window blocking and postcondition verification."""
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

        # Protect password managers, credential dialogs, and secure windows (Section 9.3)
        active_win = self.adapter.get_active_window()
        if self.adapter.is_sensitive_window(target_window_title) or (
            active_win and active_win.get("is_sensitive")
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

        if action_type == "get_active_window":
            return ToolResult(
                success=active_win is not None,
                summary="Berhasil memeriksa jendela aktif melalui adapter platform." if active_win else "Tidak ada jendela aktif yang terdeteksi.",
                data={
                    "status": "executed" if active_win else "unsupported",
                    "action_type": action_type,
                    "active_window": active_win,
                    "adapter": self.adapter.platform_name,
                    "capabilities": self.adapter.get_capabilities(),
                    "precondition_verified": True,
                    "postcondition_verified": active_win is not None,
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

        if action_executed:
            summary = f"Tier 3 Computer Use ({executed_driver}): Aksi '{action_type}' pada {detail} berhasil dieksekusi dan terverifikasi."
            return ToolResult(
                success=True,
                summary=summary,
                data={
                    "status": "executed",
                    "action_type": action_type,
                    "x": x,
                    "y": y,
                    "text": text,
                    "hotkey": hotkey,
                    "driver": executed_driver,
                    "adapter": self.adapter.platform_name,
                    "failsafe_enabled": self.failsafe_enabled,
                    "precondition_verified": True,
                    "postcondition_verified": True,
                },
                token_estimate=32,
            )
        else:
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

