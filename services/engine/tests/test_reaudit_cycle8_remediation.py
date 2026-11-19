"""Cycle 8 Re-Audit Remediation & Verification Suite.

Covers all findings from ``docs/AKSA-INDEPENDENT-REAUDIT-CYCLE-8-2026-11-19.md``:
- P1-01 & P2-02: Zero mutation of global ``sandbox_manager`` singleton + concurrent isolation
- P1-02: Canonical containment for ``expected_artifacts``, ``run_artifacts``, and API endpoints + size/time bounds
- P2-01: Removal of ``tool_executor`` bypass callback from production replay services
- P2-03: Deterministic Excel formula evaluation, error cell rejection, cached consistency, & expected cell values
- Gate 2 #5: Production ``sandbox_manager`` thread safety & workspace deletion cleanup
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import json
import os
import sys
from pathlib import Path
from typing import Any

import openpyxl
import pytest
from fastapi.testclient import TestClient

ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from app.core.agent_directory import AgentIsolationError, agent_directory_service
from app.core.agent_learning import (
    ReplayExecutionContext,
    SkillEvaluator,
    SkillVersionService,
    resolve_replay_path,
)
from app.core.orchestrator import (
    get_artifact_postcondition_breakdown,
    verify_artifact_postcondition,
)
from app.core.sandbox import (
    SandboxManager,
    SandboxViolationError,
    WorkspacePolicy,
    sandbox_manager,
)


# ===========================================================================
# P1-01, P2-01, P2-02: Scoped ContextVar Sandbox & Concurrency Safety
# ===========================================================================


def test_p2_01_and_p2_02_static_replay_isolation_invariants():
    """Verify agent_learning removes clear_all_workspaces, _workspaces mutation, and tool_executor bypass."""
    src_path = ENGINE_ROOT / "app" / "core" / "agent_learning.py"
    source_text = src_path.read_text(encoding="utf-8")
    tree = ast.parse(source_text)

    attr_names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "_workspaces" not in attr_names
    assert "clear_all_workspaces" not in attr_names
    assert "_handlers" not in attr_names

    sig_eval = inspect.signature(SkillEvaluator.replay_candidate_in_sandbox)
    assert "tool_executor" not in sig_eval.parameters
    sig_svc = inspect.signature(SkillVersionService.evaluate_and_replay_candidate)
    assert "tool_executor" not in sig_svc.parameters


def test_p2_02_replay_context_sandbox_is_frozen_and_isolated(tmp_path: Path):
    """ReplayExecutionContext builds a frozen non-singleton SandboxManager locked to its temp workspace."""
    ws = tmp_path / "ws"
    ws.mkdir()
    ctx = ReplayExecutionContext(ws)
    assert ctx.sandbox_manager is not sandbox_manager
    assert len(ctx.sandbox_manager.list_policies()) == 1
    assert ctx.sandbox_manager.list_policies()[0].allow_execute is False

    # Mutating replay sandbox MUST fail closed
    with pytest.raises(SandboxViolationError):
        ctx.sandbox_manager.clear_all_workspaces()
    with pytest.raises(SandboxViolationError):
        ctx.sandbox_manager.register_workspace(WorkspacePolicy(folder_path=str(tmp_path)))

    # Scoped context cannot bind the global singleton itself
    with pytest.raises(SandboxViolationError):
        with sandbox_manager.scoped(sandbox_manager):
            pass


@pytest.mark.asyncio
async def test_p1_01_replay_never_mutates_global_sandbox_and_runs_concurrently_without_race(
    monkeypatch, tmp_path: Path
):
    """Concurrent production file validation & workspace registration remain intact while replay runs."""
    agent_directory_service.set_root_dir(tmp_path / "aksa_data")
    prod_ws1 = (tmp_path / "prod_ws1").resolve()
    prod_ws2 = (tmp_path / "prod_ws2").resolve()
    prod_ws1.mkdir()
    prod_ws2.mkdir()
    prod_file = prod_ws1 / "active.txt"
    prod_file.write_text("production data", encoding="utf-8")

    old_policies = list(sandbox_manager.list_policies())
    sandbox_manager.clear_all_workspaces()
    sandbox_manager.register_workspace(
        WorkspacePolicy(folder_path=str(prod_ws1), allow_read=True, allow_write=True, allow_execute=False)
    )

    clear_called = []
    orig_clear = sandbox_manager.clear_all_workspaces

    def spy_clear():
        clear_called.append(True)
        return orig_clear()

    monkeypatch.setattr(sandbox_manager, "clear_all_workspaces", spy_clear)

    md = "---\nname: Concurrent Replay\ndescription: Concurrency test\n---\n# Concurrent\n"
    candidate_data = {
        "skill_id": "cand-conc-1",
        "structured_traces": [
            {
                "step_id": "create_xlsx",
                "tool_name": "excel_create_workbook",
                "input_summary": {
                    "file_path": "{out_name}",
                    "sheets_spec": [
                        {"title": "Rekap", "headers": ["Item", "Nominal"], "rows": [["A", 100], ["Sum", "=SUM(B2:B2)"]]}
                    ],
                },
                "status": "success",
            }
        ],
    }
    fixtures = [
        {"name": f"fix_{i}", "inputs": {"out_name": f"out_{i}.xlsx"}, "expected_artifacts": [f"out_{i}.xlsx"]}
        for i in range(4)
    ]

    async def concurrent_prod_ops() -> None:
        for step in range(12):
            resolved = sandbox_manager.validate_path(prod_file, mode="read")
            assert resolved == prod_file
            if step == 4:
                sandbox_manager.register_workspace(
                    WorkspacePolicy(folder_path=str(prod_ws2), allow_read=True, allow_write=False, allow_execute=False)
                )
            await asyncio.sleep(0.005)

    try:
        replay_res, _ = await asyncio.gather(
            SkillEvaluator.replay_candidate_in_sandbox(
                skill_md_content=md,
                skill_id="cand-conc-1",
                candidate_data=candidate_data,
                replay_fixtures=fixtures,
            ),
            concurrent_prod_ops(),
        )
        assert replay_res.passed is True
        assert clear_called == [], "Replay MUST NEVER call sandbox_manager.clear_all_workspaces()"

        # Concurrent workspace registration from prod_ws2 MUST still exist (not clobbered by replay snapshot!)
        final_roots = {Path(p.folder_path).resolve() for p in sandbox_manager.list_policies()}
        assert prod_ws1 in final_roots
        assert prod_ws2 in final_roots
    finally:
        monkeypatch.undo()
        sandbox_manager.clear_all_workspaces()
        for pol in old_policies:
            sandbox_manager.register_workspace(pol)


# ===========================================================================
# P1-02: Verifier Expected-Artifact Path Escape, Symlink, & API Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_p1_02_replay_blocks_expected_artifacts_escape_and_never_opens_outside_file(
    monkeypatch, tmp_path: Path
):
    """expected_artifacts cannot escape ws via traversal, absolutes, or symlinks; verifier never opens external file."""
    agent_directory_service.set_root_dir(tmp_path / "aksa_data")

    # Outside oracle target with sensitive keyword
    outside_secret = (tmp_path / "secret_payroll.xlsx").resolve()
    wb = openpyxl.Workbook()
    ws_xl = wb.active
    ws_xl.append(["Employee", "SecretToken"])
    ws_xl.append(["Alice", "ORACLE_LEAK_TOKEN_99"])
    wb.save(str(outside_secret))
    wb.close()

    import app.core.artifact_verifier_worker as worker_mod
    import app.core.orchestrator as orch_mod

    opened_paths: list[Path] = []
    orig_verify = orch_mod.verify_artifact_postcondition
    orig_worker_verify = worker_mod.verify_artifact_in_worker

    def spy_verify(art_path: Path, expected_schema: dict[str, Any] | None = None):
        opened_paths.append(art_path)
        return orig_verify(art_path, expected_schema=expected_schema)

    async def spy_worker_verify(art_path: Path, **kwargs: Any):
        opened_paths.append(art_path)
        return await orig_worker_verify(art_path, **kwargs)

    monkeypatch.setattr(orch_mod, "verify_artifact_postcondition", spy_verify)
    monkeypatch.setattr(worker_mod, "verify_artifact_in_worker", spy_worker_verify)

    md = "---\nname: Safe Replay\ndescription: Test\n---\n# Test\n"
    cand = {
        "skill_id": "cand-oracle-1",
        "structured_traces": [
            {
                "step_id": "create_xlsx",
                "tool_name": "excel_create_workbook",
                "input_summary": {
                    "file_path": "legit.xlsx",
                    "sheets_spec": [{"title": "Data", "headers": ["A", "B"], "rows": [[1, 2]]}],
                },
                "status": "success",
            }
        ],
    }

    evil_fixtures = [
        {
            "name": "parent_traversal",
            "expected_artifacts": [f"../{outside_secret.name}"],
            "expected_schema": {"required_keywords": ["ORACLE_LEAK_TOKEN_99"]},
        },
        {
            "name": "deep_traversal",
            "expected_artifacts": ["a/b/../../../secret_payroll.xlsx"],
            "expected_schema": {"required_keywords": ["ORACLE_LEAK_TOKEN_99"]},
        },
        {
            "name": "absolute_path_oracle",
            "expected_artifacts": [str(outside_secret)],
            "expected_schema": {"required_keywords": ["ORACLE_LEAK_TOKEN_99"]},
        },
    ]

    res = await SkillEvaluator.replay_candidate_in_sandbox(
        skill_md_content=md,
        skill_id="cand-oracle-1",
        candidate_data=cand,
        replay_fixtures=evil_fixtures,
    )
    assert res.passed is False
    assert res.replay_passed is False
    assert all(outside_secret.resolve() != p.resolve(strict=False) for p in opened_paths)


def test_p1_02_api_evaluate_candidate_blocks_fixture_path_escape(monkeypatch, tmp_path: Path):
    """API endpoint POST /agents/{id}/skills/{id}/evaluate rejects fixture path traversal and absolutes."""
    from app.config import settings
    from app.core.auth_context import get_default_host_principal
    from app.main import create_app

    agent_directory_service.set_root_dir(tmp_path / "aksa_data_api")
    agent_id = "agent-api-sec"
    skill_id = "cand-api-1"
    cand_dir = agent_directory_service.resolve_agent_path(agent_id, f"skills/candidates/{skill_id}")
    cand_dir.mkdir(parents=True, exist_ok=True)
    (cand_dir / "SKILL.md").write_text("---\nname: API Skill\ndescription: API test\n---\n# Skill\n", encoding="utf-8")

    outside_doc = (tmp_path / "host_confidential.txt").resolve()
    outside_doc.write_text("SECRET_API_ORACLE_VALUE", encoding="utf-8")

    (cand_dir / "candidate.json").write_text(
        json.dumps(
            {
                "skill_id": skill_id,
                "structured_traces": [
                    {
                        "step_id": "s1",
                        "tool_name": "excel_create_workbook",
                        "input_summary": {
                            "file_path": "ok.xlsx",
                            "sheets_spec": [{"title": "S", "headers": ["K", "V"], "rows": [["a", 1]]}],
                        },
                        "status": "success",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    app = create_app()
    with TestClient(app) as client:
        headers = {"X-AKSA-Auth-Token": settings.auth_token, "X-Principal-ID": get_default_host_principal()}
        resp = client.post(
            f"/api/v1/agents/{agent_id}/skills/{skill_id}/evaluate",
            headers=headers,
            json={
                "replay_fixtures": [
                    {
                        "name": "api_escape",
                        "expected_artifacts": [str(outside_doc), "../../host_confidential.txt"],
                        "expected_schema": {"required_keywords": ["SECRET_API_ORACLE_VALUE"]},
                    }
                ]
            },
        )
    assert resp.status_code == 200
    report = resp.json()["report"]
    assert report["passed"] is False
    assert report["replay_passed"] is False
    assert "path containment" in report["replay_trace"][0]["reason"].lower() or "tidak diizinkan" in report["replay_trace"][0]["reason"].lower()


@pytest.mark.asyncio
async def test_p1_02_verifier_rejects_symlinks_and_oversized_artifacts(tmp_path: Path):
    """Artifact verifier rejects symlinks and files exceeding max_bytes before invoking parsers."""
    real_txt = tmp_path / "real.txt"
    real_txt.write_text("valid content longer than 10 chars", encoding="utf-8")

    # Symlink rejected directly by verifier
    if hasattr(os, "symlink"):
        sym_txt = tmp_path / "sym.txt"
        os.symlink(real_txt, sym_txt)
        bd_sym = get_artifact_postcondition_breakdown(sym_txt)
        assert bd_sym["semantic_postcondition_passed"] is False
        assert "symlink" in bd_sym["detail"].lower()

    # Oversize rejected BEFORE parser runs
    big_json = tmp_path / "big.json"
    big_json.write_text(json.dumps({"items": list(range(500))}), encoding="utf-8")
    bd_big = get_artifact_postcondition_breakdown(big_json, expected_schema={"max_bytes": 64})
    assert bd_big["format_valid"] is False
    assert bd_big["semantic_postcondition_passed"] is False
    assert "melebihi batas" in bd_big["detail"].lower()


# ===========================================================================
# P2-03 & Gate 2 #5: Deterministic Formula Evaluation & Delete Workspace Sync
# ===========================================================================


def test_p2_03_excel_verifier_evaluates_formulas_catches_errors_and_forged_caches(tmp_path: Path):
    """Verifier rejects Excel #DIV/0! errors, forged cached values, and mismatched expected cell values."""
    # 1. Forged cached value inside workbook (e.g. cell says '=SUM(B2:B3)' while cached value lies '9999')
    forged_xlsx = tmp_path / "forged.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Item", "Nilai"])
    ws.append(["A", 100])
    ws.append(["B", 200])
    ws["A4"] = "Total"
    ws["B4"] = "=SUM(B2:B3)"
    wb.save(str(forged_xlsx))
    wb.close()

    # Valid evaluation against calculated result (300) and required formula function
    ok_true, msg_true = verify_artifact_postcondition(
        forged_xlsx,
        expected_schema={"require_formulas": True, "required_formula_functions": ["SUM"], "expected_values": {"B4": 300}},
    )
    assert ok_true is True, msg_true

    # Mismatched expected cell value MUST fail even though format and non-empty cells pass
    bd_wrong_val = get_artifact_postcondition_breakdown(
        forged_xlsx,
        expected_schema={"require_formulas": True, "expected_values": {"B4": 5000}},
    )
    assert bd_wrong_val["format_valid"] is True
    assert bd_wrong_val["content_detected"] is True
    assert bd_wrong_val["task_requirement_satisfied"] is False
    assert bd_wrong_val["semantic_postcondition_passed"] is False

    # Forge stale/lying cached <v>9999</v> in XML alongside formula '=SUM(B2:B3)'
    import zipfile
    tampered_xlsx = tmp_path / "tampered_cache.xlsx"
    with zipfile.ZipFile(forged_xlsx, "r") as zin, zipfile.ZipFile(tampered_xlsx, "w") as zout:
        for item in zin.infolist():
            raw = zin.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                xml_str = raw.decode("utf-8").replace(
                    "<f>SUM(B2:B3)</f><v></v>",
                    "<f>SUM(B2:B3)</f><v>9999</v>",
                )
                assert "<v>9999</v>" in xml_str
                raw = xml_str.encode("utf-8")
            zout.writestr(item, raw)

    bd_tampered = get_artifact_postcondition_breakdown(tampered_xlsx, expected_schema={"require_formulas": True})
    assert bd_tampered["semantic_postcondition_passed"] is False
    assert "tidak sesuai hasil kalkulasi" in bd_tampered["detail"].lower()

    # 2. Excel error cell (#DIV/0!) MUST fail
    err_xlsx = tmp_path / "error_cell.xlsx"
    wb_e = openpyxl.Workbook()
    ws_e = wb_e.active
    ws_e.append(["A", "B"])
    ws_e.append(["Test", "#DIV/0!"])
    wb_e.save(str(err_xlsx))
    wb_e.close()
    assert get_artifact_postcondition_breakdown(err_xlsx)["semantic_postcondition_passed"] is False


def test_gate2_delete_workspace_syncs_removal_from_sandbox_manager(tmp_path: Path):
    """DELETE /api/v1/workspaces/{id} removes workspace from both SQLite and live sandbox_manager."""
    from app.config import settings
    from app.core.auth_context import get_default_host_principal
    from app.main import create_app

    ws_dir = (tmp_path / "del_ws").resolve()
    ws_dir.mkdir()
    app = create_app()
    with TestClient(app) as client:
        headers = {"X-AKSA-Auth-Token": settings.auth_token, "X-Principal-ID": get_default_host_principal()}
        create_resp = client.post(
            "/api/v1/workspaces",
            headers=headers,
            json={"name": "Delete Test", "folder_path": str(ws_dir), "allow_read": True, "allow_write": True},
        )
        assert create_resp.status_code == 200
        ws_id = create_resp.json()["workspace"]["id"]
        assert any(Path(p.folder_path).resolve() == ws_dir for p in sandbox_manager.list_policies())

        del_resp = client.delete(f"/api/v1/workspaces/{ws_id}", headers=headers)
        assert del_resp.status_code == 200
        assert not any(Path(p.folder_path).resolve() == ws_dir for p in sandbox_manager.list_policies())


@pytest.mark.asyncio
async def test_p1_02_replay_rejects_escaped_run_artifacts_returned_by_tool(monkeypatch, tmp_path: Path):
    """If any replay step returns an artifact outside replay workspace, replay aborts fail-closed."""
    from app.tools.registry import ToolResult, tool_registry

    agent_directory_service.set_root_dir(tmp_path / "aksa_data_art_esc")
    outside_art = (tmp_path / "outside_tool_art.xlsx").resolve()
    outside_art.write_bytes(b"outside bytes")

    async def fake_exec_replay(name: str, replay_workspace: Path, replay_sandbox: Any = None, **kwargs: Any) -> ToolResult:
        return ToolResult(success=True, summary="Created", artifacts=[str(outside_art)])

    monkeypatch.setattr(tool_registry, "execute_replay", fake_exec_replay)
    md = "---\nname: Bad Return Artifact\ndescription: Test\n---\n# Test\n"
    cand = {
        "skill_id": "cand-bad-art",
        "structured_traces": [
            {"step_id": "s1", "tool_name": "excel_create_workbook", "input_summary": {"file_path": "ok.xlsx"}, "status": "success"}
        ],
    }
    res = await SkillEvaluator.replay_candidate_in_sandbox(
        skill_md_content=md,
        skill_id="cand-bad-art",
        candidate_data=cand,
        replay_fixtures=[{"name": "bad_ret"}],
    )
    assert res.passed is False
    assert res.replay_passed is False
    assert "melanggar isolasi" in res.replay_trace[0]["reason"].lower()
