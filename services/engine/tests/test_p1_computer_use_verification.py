"""Tests for P1.2: Computer Use Postcondition Verification, Target Window Shielding, and Failsafe Abort."""

from __future__ import annotations

import pytest

from app.tools.computer_use.gui_agent import (
    ComputerUseAdapter,
    computer_use_controller,
)


class MockWindowAdapter(ComputerUseAdapter):
    """Test mock adapter simulating predictable window and postcondition responses."""

    def __init__(self, active_title: str | None = "Document1 - Microsoft Word") -> None:
        self._title = active_title

    def get_capabilities(self) -> dict[str, dict[str, bool]]:
        return {
            "active_window_inspection": {"available": True, "implemented": True},
            "screen_capture": {"available": True, "implemented": True},
            "ui_automation_tree": {"available": True, "implemented": False},
            "native_input": {"available": True, "implemented": True},
        }

    def get_active_window(self) -> dict[str, str | bool] | None:
        if not self._title:
            return None
        is_sens = self.is_sensitive_window(self._title)
        return {
            "role": "window",
            "title": "[REDACTED_SENSITIVE_WINDOW]" if is_sens else self._title,
            "is_sensitive": is_sens,
        }


@pytest.fixture(autouse=True)
def reset_controller():
    original_adapter = computer_use_controller.adapter
    computer_use_controller.reset_emergency_stop()
    yield
    computer_use_controller.adapter = original_adapter
    computer_use_controller.reset_emergency_stop()


@pytest.mark.asyncio
async def test_capabilities_honestly_separate_available_from_implemented():
    """Verify capabilities report whether a feature is genuinely implemented or just platform-available."""
    caps = computer_use_controller.adapter.get_capabilities()
    assert "ui_automation_tree" in caps
    # ui_automation_tree should not falsely claim implemented=True
    assert caps["ui_automation_tree"]["implemented"] is False


@pytest.mark.asyncio
async def test_target_window_mismatch_blocks_execution():
    """Verify that an action targeting a specific window fails if the foreground window does not match."""
    computer_use_controller.adapter = MockWindowAdapter(active_title="Calculator")

    res = await computer_use_controller.visual_screen_action(
        action_type="click",
        x=200,
        y=200,
        target_window_title="Microsoft Excel",
    )
    assert res.success is False
    assert res.data["status"] == "target_window_mismatch"
    assert "Validasi Jendela Gagal" in res.summary
    assert res.data["precondition_verified"] is False
    assert res.data["postcondition_verified"] is False


@pytest.mark.asyncio
async def test_sensitive_window_shielding_blocks_action():
    """Verify password managers, Bitwarden, and credential dialogs block visual actions."""
    computer_use_controller.adapter = MockWindowAdapter(active_title="Bitwarden Password Vault")

    res = await computer_use_controller.visual_screen_action(
        action_type="click",
        x=200,
        y=200,
    )
    assert res.success is False
    assert res.data["status"] == "blocked_sensitive_window"
    assert "pengelola kata sandi" in res.summary


@pytest.mark.asyncio
async def test_destructive_hotkeys_blocked_without_hitl():
    """Verify Alt+F4 and Cmd+Q hotkeys are blocked as destructive actions."""
    res = await computer_use_controller.visual_screen_action(
        action_type="press_hotkey",
        hotkey=["Alt", "F4"],
    )
    assert res.success is False
    assert res.data["status"] == "destructive_action_blocked"
    assert "destruktif" in res.summary


@pytest.mark.asyncio
async def test_postcondition_verification_successful():
    """Verify that when an expected postcondition is met, success is True and postcondition_verified is True."""
    adapter = MockWindowAdapter(active_title="Laporan_Keuangan_2026.docx - Microsoft Word")
    computer_use_controller.adapter = adapter

    res = await computer_use_controller.visual_screen_action(
        action_type="click",
        x=200,
        y=200,
        expected_postcondition={"window_title_contains": "Laporan_Keuangan"},
    )
    # If simulated in headless test or executed with pyautogui
    if res.data["status"] == "simulated":
        assert res.data["postcondition_verified"] is False
    else:
        assert res.success is True
        assert res.data["status"] == "executed"
        assert res.data["postcondition_verified"] is True


@pytest.mark.asyncio
async def test_postcondition_failed_reported_honestly():
    """Verify that if postcondition is not achieved, status is postcondition_failed with success=False."""
    adapter = MockWindowAdapter(active_title="Untitled - Notepad")
    computer_use_controller.adapter = adapter

    res = await computer_use_controller.visual_screen_action(
        action_type="click",
        x=200,
        y=200,
        expected_postcondition={"window_title_contains": "Saved Successfully"},
    )
    if res.data["status"] != "simulated":
        assert res.success is False
        assert res.data["status"] == "postcondition_failed"
        assert res.data["postcondition_verified"] is False


@pytest.mark.asyncio
async def test_action_without_postcondition_reports_submitted_unverified():
    """Verify that an input sent without verified postcondition reports submitted_unverified, not fake success."""
    adapter = MockWindowAdapter(active_title="Generic Workspace")
    computer_use_controller.adapter = adapter

    res = await computer_use_controller.visual_screen_action(
        action_type="click",
        x=200,
        y=200,
    )
    if res.data["status"] != "simulated":
        assert res.success is False
        assert res.data["status"] == "submitted_unverified"
        assert res.data["postcondition_verified"] is False

