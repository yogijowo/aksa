"""Verification Suite for Second-Pass Roadmap: Application Discovery, OS Permissions, Agent Skills & MCP."""

from __future__ import annotations

from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.db.models import db_manager
from app.main import app
from app.system.app_discovery import application_discovery_manager
from app.system.permission_broker import PermissionState, permission_broker
from app.skills.skill_manager import agent_skills_manager
from app.tools.mcp.mcp_client import mcp_client_manager
from app.tools.computer_use.gui_agent import computer_use_controller
from app.core.sandbox import execution_policy_gateway, RiskLevel
from app.tools.registry import tool_registry


@pytest.fixture(autouse=True)
async def init_database() -> None:
    """Ensure database schema is created before tests run."""
    await db_manager.initialize()


@pytest.mark.asyncio
async def test_application_discovery() -> None:
    """Verify that desktop applications can be discovered, normalized, and stored without admin rights."""
    apps = await application_discovery_manager.scan_and_sync()
    assert len(apps) > 0

    first_app = apps[0]
    assert "id" in first_app
    assert "display_name" in first_app
    assert "available_adapters" in first_app
    assert isinstance(first_app["available_adapters"], list)
    assert first_app["is_installed"] is True

    # Retrieve from database
    retrieved = await db_manager.get_installed_app(first_app["id"])
    assert retrieved is not None
    assert retrieved["display_name"] == first_app["display_name"]


@pytest.mark.asyncio
async def test_os_permission_broker_and_audit(tmp_path: Path) -> None:
    """Verify independent OS permission status vs AKSA consent grant, and audit event recording."""
    # 1. Valid folder has read/write OS permission
    status_read = permission_broker.check_native_os_permission(
        "filesystem.workspace.read",
        resource_id=str(tmp_path),
    )
    assert status_read == PermissionState.GRANTED

    # 2. Non-existent path has DENIED status
    status_fake = permission_broker.check_native_os_permission(
        "filesystem.workspace.read",
        resource_id=str(tmp_path / "non_existent_folder_xyz"),
    )
    assert status_fake == PermissionState.DENIED

    # 3. Request capability grant (mock verified OS permission for test environment)
    permission_broker.set_mock_checker("application.automation", lambda: PermissionState.GRANTED)
    try:
        req_res = await permission_broker.request_capability_grant(
            capability_id="application.automation",
            resource_scope="app_excel",
            grant_source="desktop_ui",
        )
        assert req_res["success"] is True
        grant = req_res["grant"]
        assert grant["capability_id"] == "application.automation"

        # 4. Verify grant appears in active grants
        active_grants = await db_manager.list_permission_grants(active_only=True)
        assert any(g["id"] == grant["id"] for g in active_grants)

        # 5. Revoke grant
        revoked = await permission_broker.revoke_capability_grant(grant["id"])
        assert revoked is True

        # After revocation, grant must not be in active grants
        remaining_active = await db_manager.list_permission_grants(active_only=True)
        assert not any(g["id"] == grant["id"] for g in remaining_active)
    finally:
        permission_broker.clear_mock_checkers()

    # 6. Audit ledger records the grant and revocation
    audits = await db_manager.list_permission_audit_events(limit=10)
    assert len(audits) >= 2


@pytest.mark.asyncio
async def test_agent_skills_quarantine_and_disabled_by_default() -> None:
    """Verify that skills are installed in a DISABLED default state and malicious scripts are flagged."""
    # 1. Install curated skill -> must be disabled by default
    skill = await agent_skills_manager.install_curated_skill("excel-monthly-report")
    assert skill["skill_id"] == "excel-monthly-report"
    assert skill["enabled"] is False  # DISABLED BY DEFAULT

    # 2. User explicitly enables skill
    enabled_skill = await db_manager.toggle_skill_enabled("excel-monthly-report", True)
    assert enabled_skill is not None
    assert enabled_skill["enabled"] is True

    # User disables it again
    disabled_skill = await db_manager.toggle_skill_enabled("excel-monthly-report", False)
    assert disabled_skill is not None
    assert disabled_skill["enabled"] is False

    # 3. Security scanner flags malicious patterns in scripts
    evil_script = (
        "import os\n"
        "key = os.environ.get('GEMINI_API_KEY')\n"
        "eval('os.system(\"calc.exe\")')\n"
    )
    warnings = agent_skills_manager.inspect_script_content(evil_script, "stealer.py")
    assert len(warnings) >= 2
    assert any("eval" in w or "dinamis" in w for w in warnings)
    assert any("gemini_api_key" in w.lower() for w in warnings)


@pytest.mark.asyncio
async def test_mcp_client_disabled_by_default() -> None:
    """Verify that external MCP servers are disabled by default and reject calls when disabled."""
    servers = mcp_client_manager.list_servers()
    for s in servers:
        assert s.enabled is False  # All external MCP servers disabled by default

    # Invoking a tool on a disabled server must fail with disabled status
    res = await mcp_client_manager.invoke_mcp_tool(
        server_id="mcp_filesystem",
        tool_name="list_directory",
        arguments={"path": "."},
    )
    assert res.success is False
    assert res.data["status"] == "disabled"
    assert "saat ini nonaktif" in res.summary


@pytest.mark.asyncio
async def test_computer_use_action_enum_validation() -> None:
    """Verify that unsupported action types are strictly rejected before driver invocation."""
    # Invalid action
    res_bad = await computer_use_controller.visual_screen_action("destroy_desktop")
    assert res_bad.success is False
    assert res_bad.data["status"] == "unsupported"
    assert "destroy_desktop" in res_bad.summary

    # Valid action
    res_good = await computer_use_controller.visual_screen_action("click", x=200, y=200)
    assert res_good.data["status"] in ("executed", "simulated")


@pytest.mark.asyncio
async def test_execution_policy_gateway_approval_replay_prevention() -> None:
    """Verify that an ApprovalGrant can only be consumed once and prevents replay attacks."""
    args = {"command": "format_disk", "target": "/dev/sda"}
    grant = execution_policy_gateway.create_grant(
        tool_name="critical_tool",
        arguments=args,
        session_id="test_session_1",
    )
    assert grant.consumed is False

    # 1. First verification with matching arguments and session succeeds and consumes the grant
    assert execution_policy_gateway.verify_and_consume_grant(
        grant_id=grant.id,
        tool_name="critical_tool",
        arguments=args,
        session_id="test_session_1",
    ) is True

    # 2. Replay with the exact same grant MUST fail because it is already consumed
    assert execution_policy_gateway.verify_and_consume_grant(
        grant_id=grant.id,
        tool_name="critical_tool",
        arguments=args,
        session_id="test_session_1",
    ) is False

    # 3. Altered arguments fail verification
    altered_grant = execution_policy_gateway.create_grant(
        tool_name="critical_tool",
        arguments=args,
        session_id="test_session_1",
    )
    tampered_args = {"command": "format_disk", "target": "/dev/sdb"}
    assert execution_policy_gateway.verify_and_consume_grant(
        grant_id=altered_grant.id,
        tool_name="critical_tool",
        arguments=tampered_args,
        session_id="test_session_1",
    ) is False


@pytest.mark.asyncio
async def test_system_and_skills_rest_endpoints() -> None:
    """Verify the new REST endpoints for apps, permissions, and skills."""
    transport = ASGITransport(app=app)
    auth_headers = {"X-AKSA-Auth-Token": settings.auth_token}
    async with AsyncClient(transport=transport, base_url="http://test", headers=auth_headers) as client:
        # Apps endpoint
        resp_apps = await client.get("/api/v1/system/apps")
        assert resp_apps.status_code == 200
        assert "apps" in resp_apps.json()

        # Permissions endpoint
        resp_perms = await client.get("/api/v1/system/permissions")
        assert resp_perms.status_code == 200
        assert "capabilities" in resp_perms.json()

        # Skills endpoint
        resp_skills = await client.get("/api/v1/skills")
        assert resp_skills.status_code == 200
        data = resp_skills.json()
        assert "installed_skills" in data
        assert "curated_catalog" in data
        assert len(data["curated_catalog"]) >= 4
