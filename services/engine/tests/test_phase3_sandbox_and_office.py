"""Phase 3 Verification Suite: Workspace Sandbox, Tier 1 Office Engine, Tier 2 OS Bridge/uv/MCP, Tier 3 Computer Use."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.sandbox import RiskLevel, SandboxManager, SandboxViolationError, WorkspacePolicy, sandbox_manager
from app.main import app
from app.tools import tool_registry
from app.tools.computer_use.gui_agent import computer_use_controller


@pytest.mark.asyncio
async def test_sandbox_path_jail_and_auto_backup(tmp_path: Path) -> None:
    """Verify strict path jail, read/write/execute permission checks, and automatic .aksa_backup snapshots."""
    sm = SandboxManager()
    allowed_dir = tmp_path / "workspace_aman"
    allowed_dir.mkdir()
    outside_dir = tmp_path / "rahasia_sistem"
    outside_dir.mkdir()

    sm.register_workspace(
        WorkspacePolicy(
            folder_path=str(allowed_dir),
            allow_read=True,
            allow_write=True,
            allow_execute=False,
        )
    )

    # Inside workspace is allowed
    valid_file = allowed_dir / "catatan.txt"
    valid_file.write_text("Versi 1", encoding="utf-8")
    resolved = sm.validate_path(valid_file, mode="read")
    assert resolved == valid_file.resolve()

    # Outside workspace must raise SandboxViolationError
    with pytest.raises(SandboxViolationError):
        sm.validate_path(outside_dir / "password.txt", mode="read")

    # Execute mode is disabled on this workspace
    with pytest.raises(SandboxViolationError):
        sm.validate_path(valid_file, mode="execute")

    # Auto-backup before modifying existing file
    backup_path = sm.backup_before_modify(valid_file)
    assert backup_path is not None
    assert backup_path.exists()
    assert backup_path.parent.name == ".aksa_backup"
    assert backup_path.read_text(encoding="utf-8") == "Versi 1"


@pytest.mark.asyncio
async def test_hitl_approval_lifecycle() -> None:
    """Verify Human-in-the-Loop approval creation, listing, and resolution."""
    req = await sandbox_manager.create_hitl_request(
        tool_name="run_custom_python_task",
        title_id="Konfirmasi Eksekusi Skrip Python",
        description_id="Agen meminta izin menjalankan skrip analisis di Folder Kerja.",
        risk_level=RiskLevel.HIGH,
    )
    assert req.status == "pending"

    resolved = await sandbox_manager.resolve_hitl_request(req.id, approved=True)
    assert resolved.status == "approved"
    assert await sandbox_manager.wait_for_hitl_decision(req.id, timeout=1.0) is True


@pytest.mark.asyncio
async def test_tier1_excel_word_ppt_pdf_and_filesystem_tools(tmp_path: Path) -> None:
    """Verify all Tier 1 Office & Filesystem tools generate real valid files inside the sandbox."""
    sandbox_manager.register_workspace(
        WorkspacePolicy(
            folder_path=str(tmp_path),
            allow_read=True,
            allow_write=True,
            allow_execute=True,
        )
    )

    # 1. Excel: Create, Inspect, Modify (with auto-backup)
    xlsx_path = tmp_path / "Laporan_Keuangan.xlsx"
    res_xlsx = await tool_registry.execute(
        "excel_create_workbook",
        file_path=str(xlsx_path),
    )
    assert res_xlsx.success is True
    assert xlsx_path.exists()

    res_inspect_xlsx = await tool_registry.execute("excel_inspect", file_path=str(xlsx_path))
    assert res_inspect_xlsx.success is True
    assert len(res_inspect_xlsx.data["sheets"]) == 1
    assert any("=SUM" in f for f in res_inspect_xlsx.data["sheets"][0]["formulas_sample"])

    res_mod_xlsx = await tool_registry.execute(
        "excel_modify_cells",
        file_path=str(xlsx_path),
        cell_updates={"B2": "Operasional Pusat"},
        append_rows=[[4, "Cadangan Kas", 10000000, 8000000, "=C6-D6"]],
    )
    assert res_mod_xlsx.success is True
    assert res_mod_xlsx.data["backup_path"] is not None

    # 2. Word: Create, Inspect, Fill Template
    docx_path = tmp_path / "Surat_Resmi.docx"
    res_docx = await tool_registry.execute(
        "word_create_document",
        file_path=str(docx_path),
        title="Surat Penawaran Kerja Sama",
        style_preset="surat_resmi",
        sections=[
            {
                "heading": "Pendahuluan",
                "paragraphs": ["Kepada Yth. {{nama_klien}} pada tanggal {{tanggal}}."],
            }
        ],
    )
    assert res_docx.success is True
    assert docx_path.exists()

    res_inspect_docx = await tool_registry.execute("word_inspect", file_path=str(docx_path))
    assert res_inspect_docx.success is True

    filled_docx_path = tmp_path / "Surat_Resmi_Terisi.docx"
    res_fill = await tool_registry.execute(
        "word_fill_template",
        template_path=str(docx_path),
        output_path=str(filled_docx_path),
        replacements={"nama_klien": "PT Maju Bersama", "tanggal": "17 November 2026"},
    )
    assert res_fill.success is True
    assert res_fill.data["replacements_applied"] == 2
    assert filled_docx_path.exists()

    # 3. PowerPoint: Create Presentation
    pptx_path = tmp_path / "Presentasi_Direksi.pptx"
    res_pptx = await tool_registry.execute(
        "ppt_create_presentation",
        file_path=str(pptx_path),
        title="Evaluasi Kinerja Q4 2026",
    )
    assert res_pptx.success is True
    assert pptx_path.exists()
    assert res_pptx.data["slide_count"] >= 3

    # 4. PDF: Generate Report, Extract Markdown, Merge/Split
    pdf_path = tmp_path / "Ringkasan_Audit.pdf"
    res_pdf = await tool_registry.execute(
        "pdf_generate_report",
        file_path=str(pdf_path),
        title="Laporan Audit Internal 2026",
    )
    assert res_pdf.success is True
    assert pdf_path.exists()

    res_pdf_md = await tool_registry.execute("pdf_extract_markdown", file_path=str(pdf_path))
    assert res_pdf_md.success is True
    assert "Halaman 1" in res_pdf_md.data["markdown"]

    merged_pdf_path = tmp_path / "Gabungan_Audit.pdf"
    res_pdf_merge = await tool_registry.execute(
        "pdf_merge_split",
        input_paths=[str(pdf_path), str(pdf_path)],
        output_path=str(merged_pdf_path),
        mode="merge",
    )
    assert res_pdf_merge.success is True
    assert res_pdf_merge.data["page_count"] == 2

    # 5. Scoped Filesystem Tools
    res_list = await tool_registry.execute("list_workspace_files", workspace_path=str(tmp_path))
    assert res_list.success is True
    assert len(res_list.data["items"]) >= 5

    res_outline = await tool_registry.execute("inspect_file_outline", file_path=str(xlsx_path))
    assert res_outline.success is True
    assert "sheets" in res_outline.data


@pytest.mark.asyncio
async def test_tier2_os_bridge_uv_runner_and_mcp(tmp_path: Path) -> None:
    """Verify Tier 2 live Office controller, isolated Python script runner, and MCP client."""
    sandbox_manager.register_workspace(
        WorkspacePolicy(
            folder_path=str(tmp_path),
            allow_read=True,
            allow_write=True,
            allow_execute=True,
        )
    )

    # OS Bridge dry_run check
    res_os = await tool_registry.execute(
        "control_live_office_app",
        app_name="Microsoft Excel",
        action="read_active_sheet",
        dry_run=True,
    )
    assert res_os.success is True

    # Self-extending Python runner creating an artifact in workspace
    script = (
        "from pathlib import Path\n"
        "Path('hasil_hitung.csv').write_text('item,nilai\\nAI,100\\n', encoding='utf-8')\n"
        "print('CSV dibuat sukses')\n"
    )
    res_py = await tool_registry.execute(
        "run_custom_python_task",
        working_dir=str(tmp_path),
        script_code=script,
    )
    assert res_py.success is True
    assert any("hasil_hitung.csv" in art for art in res_py.artifacts)

    # MCP tool invocation
    res_mcp = await tool_registry.execute(
        "invoke_mcp_tool",
        server_id="mcp_filesystem",
        tool_name="list_directory",
        arguments={"path": str(tmp_path)},
    )
    assert res_mcp.success is True


@pytest.mark.asyncio
async def test_tier3_computer_use_and_failsafe(tmp_path: Path) -> None:
    """Verify Tier 3 screen capture, visual actions, failsafe corner abort, and emergency stop."""
    sandbox_manager.register_workspace(
        WorkspacePolicy(folder_path=str(tmp_path), allow_read=True, allow_write=True)
    )
    computer_use_controller.reset_emergency_stop()

    res_cap = await tool_registry.execute("capture_screen_and_a11y", workspace_path=str(tmp_path))
    assert res_cap.success is True
    assert Path(res_cap.data["screenshot_path"]).exists()

    res_click = await tool_registry.execute(
        "visual_screen_action",
        action_type="click",
        x=320,
        y=240,
    )
    assert res_click.data["action_type"] == "click"
    if res_click.data["driver"] == "pyautogui":
        assert res_click.success is True
        assert res_click.data["status"] == "executed"
    else:
        assert res_click.success is False
        assert res_click.data["status"] == "simulated"

    # Corner coordinate (0, 0) must trigger Failsafe Corner Abort
    with pytest.raises(RuntimeError, match="Failsafe Corner Abort"):
        await tool_registry.execute(
            "visual_screen_action",
            action_type="click",
            x=0,
            y=0,
        )

    # Emergency stop is now active, subsequent actions must be blocked until reset
    res_blocked = await tool_registry.execute(
        "visual_screen_action",
        action_type="type_text",
        text="halo",
    )
    assert res_blocked.success is False
    computer_use_controller.reset_emergency_stop()


@pytest.mark.asyncio
async def test_phase3_rest_endpoints(tmp_path: Path) -> None:
    """Verify Phase 3 REST API endpoints for tools, HITL approvals, and MCP servers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp_tools = await client.get("/api/v1/tools")
        assert resp_tools.status_code == 200
        tool_names = {t["name"] for t in resp_tools.json()["tools"]}
        assert "excel_create_workbook" in tool_names
        assert "word_create_document" in tool_names
        assert "ppt_create_presentation" in tool_names
        assert "pdf_generate_report" in tool_names

        resp_mcp = await client.get("/api/v1/mcp/servers")
        assert resp_mcp.status_code == 200
        assert len(resp_mcp.json()["servers"]) >= 3

        resp_hitl = await client.post(
            "/api/v1/sandbox/approvals",
            json={
                "tool_name": "visual_screen_action",
                "title_id": "Izin Kontrol Mouse Tier 3",
                "description_id": "Operator PC ingin mengklik tombol Simpan pada aplikasi desktop.",
                "risk_level": "high",
            },
        )
        assert resp_hitl.status_code == 200
        req_id = resp_hitl.json()["approval"]["id"]

        resp_resolve = await client.post(
            f"/api/v1/sandbox/approvals/{req_id}/resolve",
            json={"approved": True},
        )
        assert resp_resolve.status_code == 200
        assert resp_resolve.json()["approval"]["status"] == "approved"

