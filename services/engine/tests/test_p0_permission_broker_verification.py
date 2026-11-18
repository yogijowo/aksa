"""Tests for P0.4: Native OS Permission Broker Runtime Verification and Fail-Closed Enforcement."""

from __future__ import annotations

import os
import sys
from pathlib import Path
import pytest

from app.db.models import db_manager
from app.system.permission_broker import (
    AKSAConsentState,
    PermissionState,
    permission_broker,
)


@pytest.fixture(autouse=True)
def clean_broker_mocks():
    """Ensure mock checkers are cleared after each test."""
    permission_broker.clear_mock_checkers()
    yield
    permission_broker.clear_mock_checkers()


@pytest.mark.asyncio
async def test_permission_states_enum_coverage():
    """Verify that all required standardized permission states exist."""
    expected_states = {
        "UNSUPPORTED",
        "NOT_REQUESTED",
        "NEEDS_USER_ACTION",
        "PENDING",
        "GRANTED",
        "DENIED",
        "REVOKED",
        "ERROR",
    }
    actual_states = {s.value for s in PermissionState}
    assert expected_states.issubset(actual_states)


@pytest.mark.asyncio
async def test_permission_not_blindly_inferred_from_platform():
    """Verify capabilities are not blindly marked GRANTED without genuine verification."""
    # Screen capture on macOS without TCC or with mock denied should never be GRANTED
    permission_broker.set_mock_checker("screen.capture", lambda: PermissionState.NEEDS_USER_ACTION)
    state = permission_broker.check_native_os_permission("screen.capture")
    assert state == PermissionState.NEEDS_USER_ACTION

    # Accessibility inspect mock denied
    permission_broker.set_mock_checker("accessibility.inspect", lambda: PermissionState.DENIED)
    state_ax = permission_broker.check_native_os_permission("accessibility.inspect")
    assert state_ax == PermissionState.DENIED


@pytest.mark.asyncio
async def test_request_grant_rejected_when_native_os_permission_not_granted():
    """Verify that user consent cannot be granted if native OS permission is NEEDS_USER_ACTION or DENIED (fail-closed)."""
    # 1. Simulate OS permission needing user action (e.g. macOS TCC modal)
    permission_broker.set_mock_checker("screen.capture", lambda: PermissionState.NEEDS_USER_ACTION)

    res = await permission_broker.request_capability_grant(
        capability_id="screen.capture",
        resource_scope="session",
        grant_source="desktop_ui",
    )
    assert res["success"] is False
    assert res["os_status"] == PermissionState.NEEDS_USER_ACTION.value
    assert "memerlukan izin di Pengaturan Sistem Operasi" in res["message"]

    # 2. Simulate OS permission denied (e.g. missing DC or restricted account)
    permission_broker.set_mock_checker("screen.capture", lambda: PermissionState.DENIED)

    res_denied = await permission_broker.request_capability_grant(
        capability_id="screen.capture",
        resource_scope="session",
        grant_source="desktop_ui",
    )
    assert res_denied["success"] is False
    assert res_denied["os_status"] == PermissionState.DENIED.value
    assert "Sistem Operasi menolak akses" in res_denied["message"]


@pytest.mark.asyncio
async def test_runtime_recheck_revokes_consent_if_os_permission_revoked(tmp_path: Path):
    """Verify that if an OS permission is revoked after grant, has_active_consent immediately returns False."""
    # Step 1: Mock permission as GRANTED initially
    permission_broker.set_mock_checker("application.automation", lambda: PermissionState.GRANTED)

    grant_res = await permission_broker.request_capability_grant(
        capability_id="application.automation",
        resource_scope="workspace",
        grant_source="desktop_ui",
    )
    assert grant_res["success"] is True
    grant = grant_res["grant"]

    # Consent is active while OS permission is GRANTED
    assert await permission_broker.has_active_consent("application.automation", "workspace") is True

    # Step 2: User revokes permission at OS level (e.g. toggled off in OS settings)
    permission_broker.set_mock_checker("application.automation", lambda: PermissionState.NEEDS_USER_ACTION)

    # Runtime recheck must return False despite existing DB grant!
    assert await permission_broker.has_active_consent("application.automation", "workspace") is False

    # Cleanup grant
    await permission_broker.revoke_capability_grant(grant["id"])


@pytest.mark.asyncio
async def test_linux_wayland_and_x11_detection(monkeypatch):
    """Verify Linux Wayland returns NEEDS_USER_ACTION and headless X11 returns DENIED."""
    permission_broker.clear_mock_checkers()

    # Simulate Linux
    monkeypatch.setattr(sys, "platform", "linux")

    # 1. Wayland session
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    state_wayland = permission_broker.check_native_os_permission("screen.capture")
    assert state_wayland == PermissionState.NEEDS_USER_ACTION

    # 2. X11 without DISPLAY
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.delenv("DISPLAY", raising=False)
    state_x11_headless = permission_broker.check_native_os_permission("screen.capture")
    assert state_x11_headless == PermissionState.DENIED

    # 3. X11 with DISPLAY
    monkeypatch.setenv("DISPLAY", ":0")
    state_x11_ok = permission_broker.check_native_os_permission("screen.capture")
    assert state_x11_ok == PermissionState.GRANTED


@pytest.mark.asyncio
async def test_capability_status_contains_revocation_guide():
    """Verify all capabilities report clear revocation guidelines in statuses."""
    statuses = await permission_broker.get_all_capability_statuses()
    assert len(statuses) > 0
    for s in statuses:
        assert "revocation_guide" in s
        assert len(s["revocation_guide"]) > 0
        assert "os_status" in s
        assert "aksa_status" in s

