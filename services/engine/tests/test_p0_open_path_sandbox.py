"""Regression tests for P0-1: Security hardening of /system/open-path.

Validates that /system/open-path enforces:
1. Strict sandbox jail (rejecting /etc/hosts, /Applications/Calculator.app, or UNC paths with 403).
2. Extension allowlist (.docx, .xlsx, .pptx, .pdf, .txt, .csv, .md, .png, .jpg, .jpeg, .json).
3. Rejection of executable scripts (.command, .sh, .bat, .exe) with 400.
4. Rejection of macOS app bundles (*.app) with 403.
5. Workspace root directory allowed; arbitrary subdirectories rejected with 400.
6. Structured audit logging via observability_manager.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.routes import SAFE_OPEN_EXTENSIONS
from app.config import settings
from app.core.observability import observability_manager
from app.core.sandbox import WorkspacePolicy, sandbox_manager
from app.db.models import db_manager
from app.main import create_app


@pytest.fixture(autouse=True)
async def setup_test_db(tmp_path: Path):
    await db_manager.initialize()
    yield


@pytest.mark.asyncio
async def test_p0_open_path_sandbox_and_extension_security(tmp_path: Path) -> None:
    # 1. Create a temporary authorized workspace
    ws_dir = tmp_path / "authorized_workspace"
    ws_dir.mkdir(parents=True, exist_ok=True)
    ws_real = Path(os.path.realpath(ws_dir))

    # Register in DB and sandbox
    ws_record = await db_manager.upsert_workspace({
        "name": "Workspace P0-1 Test",
        "folder_path": str(ws_real),
        "allow_read": True,
        "allow_write": True,
    })
    sandbox_manager.register_workspace(
        WorkspacePolicy(folder_path=str(ws_real), allow_read=True, allow_write=True)
    )

    app = create_app()
    transport = ASGITransport(app=app)
    auth_headers = {"X-AKSA-Auth-Token": settings.auth_token}

    async with AsyncClient(transport=transport, base_url="http://test", headers=auth_headers) as client:
        # Mock subprocess / os.startfile to prevent actual GUI launches during test
        with patch("subprocess.Popen") as mock_popen, patch("os.startfile", create=True) as mock_startfile:
            # Case A: External system file (/etc/hosts or /Applications/Calculator.app) -> 403
            resp_hosts = await client.post("/api/v1/system/open-path", json={"path": "/etc/hosts"})
            assert resp_hosts.status_code == 403, f"Expected 403 for /etc/hosts, got {resp_hosts.status_code}"

            calc_path = "/Applications/Calculator.app"
            resp_calc = await client.post("/api/v1/system/open-path", json={"path": calc_path})
            assert resp_calc.status_code == 403, f"Expected 403 for /Applications/Calculator.app, got {resp_calc.status_code}"

            # Case B: UNC / Network paths -> 403
            resp_unc = await client.post(
                "/api/v1/system/open-path",
                json={"path": "\\\\192.168.1.1\\share\\payload.docx"},
            )
            assert resp_unc.status_code == 403

            # Case C: Disallowed executable inside authorized workspace (x.command, script.sh) -> 400
            bad_script = ws_real / "x.command"
            bad_script.write_text("#!/bin/bash\necho test\n", encoding="utf-8")
            resp_script = await client.post(
                "/api/v1/system/open-path",
                json={"path": str(bad_script)},
            )
            assert resp_script.status_code == 400, f"Expected 400 for x.command, got {resp_script.status_code}"
            assert "tidak diizinkan" in resp_script.json().get("detail", "")

            # Case D: App bundle directory inside workspace (*.app) -> 403
            app_bundle = ws_real / "Malicious.app"
            app_bundle.mkdir()
            resp_bundle = await client.post(
                "/api/v1/system/open-path",
                json={"path": str(app_bundle)},
            )
            assert resp_bundle.status_code == 403
            assert "bundle aplikasi" in resp_bundle.json().get("detail", "")

            # Case E: Arbitrary directory inside workspace -> 400
            sub_dir = ws_real / "subfolder"
            sub_dir.mkdir()
            resp_subdir = await client.post(
                "/api/v1/system/open-path",
                json={"path": str(sub_dir)},
            )
            assert resp_subdir.status_code == 400
            assert "root Folder Kerja" in resp_subdir.json().get("detail", "")

            # Case F: Authorized workspace root directory -> 200
            resp_ws_root = await client.post(
                "/api/v1/system/open-path",
                json={"path": str(ws_real)},
            )
            assert resp_ws_root.status_code == 200
            assert resp_ws_root.json()["success"] is True

            # Case G: Valid file with safe extension inside workspace (report.docx) -> 200
            good_doc = ws_real / "report.docx"
            good_doc.write_bytes(b"PK\x03\x04 fake docx")
            resp_doc = await client.post(
                "/api/v1/system/open-path",
                json={"path": str(good_doc)},
            )
            assert resp_doc.status_code == 200
            assert resp_doc.json()["success"] is True
            assert resp_doc.json()["name"] == "report.docx"

            # Case H: Relative path matching a file in authorized workspace -> 200
            resp_rel = await client.post(
                "/api/v1/system/open-path",
                json={"path": "report.docx"},
            )
            assert resp_rel.status_code == 200
            assert resp_rel.json()["success"] is True

            # Case I: Symlink escaping the workspace -> 403
            symlink_escape = ws_real / "sneaky_hosts.docx"
            try:
                symlink_escape.symlink_to("/etc/hosts")
                resp_symlink = await client.post(
                    "/api/v1/system/open-path",
                    json={"path": str(symlink_escape)},
                )
                assert resp_symlink.status_code == 403
            except OSError:
                pass  # Ignore if OS permissions prevent creating symlink in test env

            # Case J: Verify audit logs captured open events
            logs = observability_manager.get_debug_logs(limit=20)
            open_events = [l for l in logs if l.get("component") == "SYSTEM_OPEN_PATH"]
            assert len(open_events) > 0

    # Case K: Unauthenticated client without token in production/auth mode -> 401
    orig_dev = settings.dev_mode
    try:
        settings.dev_mode = False
        async with AsyncClient(transport=transport, base_url="http://test") as unauth_client:
            resp_unauth = await unauth_client.post(
                "/api/v1/system/open-path",
                json={"path": str(good_doc)},
            )
            assert resp_unauth.status_code == 401
            assert resp_unauth.json()["code"] == "UNAUTHORIZED_SIDECAR_TOKEN"
    finally:
        settings.dev_mode = orig_dev
