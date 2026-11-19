"""Cycle 9 Re-Audit Remediation & Hardening Verification Suite.

Covers all findings from ``docs/AKSA-INDEPENDENT-REAUDIT-CYCLE-9-2026-11-19.md``:
- P2-01: Un-overridable server max_bytes limit in API, ReplayExecutionContext, & verifier
- P2-02: Fail-closed handling of unsupported Excel formulas (NEVER trust cached <v> values)
- P2-03: Killable subprocess artifact verifier worker that terminates stalled parsers on timeout
- P2-04: Strict replay payload bounds (fixture count, expected_artifacts, input_files, total bytes)
- Section 6 #3: Pre-parser OOXML ZIP bomb / ratio / entry traversal / worksheet dimension guards
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Any

import openpyxl
import pytest
from starlette.testclient import TestClient

ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from app.config import settings
from app.core.agent_directory import agent_directory_service
from app.core.agent_learning import (
    MAX_FIXTURE_EXPECTED_ARTIFACTS,
    MAX_FIXTURE_INPUT_FILE_BYTES,
    MAX_FIXTURE_INPUT_FILES,
    MAX_REPLAY_FIXTURES,
    MAX_TOTAL_REPLAY_PAYLOAD_BYTES,
    ReplayExecutionContext,
    SkillEvaluator,
    validate_replay_fixtures_budget,
)
from app.core.artifact_verifier_worker import verify_artifact_in_worker
from app.core.auth_context import get_default_host_principal
from app.core.orchestrator import (
    MAX_ARTIFACT_VERIFY_BYTES,
    get_artifact_postcondition_breakdown,
    sanitize_verifier_schema,
    verify_artifact_postcondition,
)
from app.main import create_app


# ===========================================================================
# P2-01: Un-Overridable Server File Size Cap Across Verifier & Replay API
# ===========================================================================


def test_p2_01_sanitize_verifier_schema_clamps_max_bytes_strictly():
    """Callers cannot raise max_bytes above MAX_ARTIFACT_VERIFY_BYTES or set invalid sizes."""
    assert sanitize_verifier_schema({"max_bytes": 10**12})["max_bytes"] == MAX_ARTIFACT_VERIFY_BYTES
    assert sanitize_verifier_schema({"max_bytes": -5})["max_bytes"] == 1
    assert sanitize_verifier_schema({"max_bytes": "not_an_int"})["max_bytes"] == MAX_ARTIFACT_VERIFY_BYTES
    assert sanitize_verifier_schema({"max_bytes": 512})["max_bytes"] == 512
    assert sanitize_verifier_schema(None)["max_bytes"] == MAX_ARTIFACT_VERIFY_BYTES


def test_p2_01_api_ignores_large_max_bytes_override_and_rejects_oversize_artifact(
    monkeypatch, tmp_path: Path
):
    """API caller passing huge expected_schema.max_bytes still gets blocked by server max_bytes limit."""
    # Lower internal server limit during test so we prove enforcement without writing >25MB to disk
    monkeypatch.setattr(ReplayExecutionContext, "MAX_VERIFIER_FILE_BYTES", 256)

    agent_directory_service.set_root_dir(tmp_path / "aksa_data_p201_c9")
    agent_id = "agent-c9-p201"
    skill_id = "cand-c9-p201"
    cand_dir = agent_directory_service.resolve_agent_path(agent_id, f"skills/candidates/{skill_id}")
    cand_dir.mkdir(parents=True, exist_ok=True)
    (cand_dir / "SKILL.md").write_text("---\nname: Cap Test\ndescription: Cap\n---\n# Cap\n", encoding="utf-8")
    (cand_dir / "candidate.json").write_text(
        json.dumps(
            {
                "skill_id": skill_id,
                "structured_traces": [
                    {
                        "step_id": "s1",
                        "tool_name": "excel_create_workbook",
                        "input_summary": {
                            "file_path": "report.xlsx",
                            "sheets_spec": [{"title": "Data", "headers": ["A", "B"], "rows": [["X", 10]]}],
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
                        "name": "override_attempt",
                        "expected_artifacts": ["report.xlsx"],
                        "expected_schema": {"max_bytes": 999_999_999},
                    }
                ]
            },
        )
    assert resp.status_code == 200
    report = resp.json()["report"]
    assert report["passed"] is False
    assert report["replay_passed"] is False
    assert "melebihi batas" in report["replay_trace"][0]["reason"].lower()


# ===========================================================================
# P2-02: Unsupported Excel Formulas Fail Closed (Never Trust Cached Values)
# ===========================================================================


def test_p2_02_unsupported_excel_formulas_reject_forged_or_unverified_cached_values(tmp_path: Path):
    """Workbook containing an unsupported formula (e.g. VLOOKUP/IF) fails closed even with fake <v> cache."""
    f_raw = tmp_path / "unsupported_fml.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Key", "Amount", "Lookup"])
    ws.append(["A1", 100, 500])
    ws["C3"] = "=VLOOKUP(A2,A2:B2,2,FALSE)"
    wb.save(str(f_raw))
    wb.close()

    # Inject a forged cached value <v>999999</v> into sheet1.xml for the unsupported formula
    f_forged = tmp_path / "unsupported_forged.xlsx"
    with zipfile.ZipFile(f_raw, "r") as zin, zipfile.ZipFile(f_forged, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                xml_str = data.decode("utf-8").replace(
                    "<f>VLOOKUP(A2,A2:B2,2,FALSE)</f><v></v>",
                    "<f>VLOOKUP(A2,A2:B2,2,FALSE)</f><v>999999</v>",
                )
                assert "<v>999999</v>" in xml_str
                data = xml_str.encode("utf-8")
            zout.writestr(item, data)

    bd = get_artifact_postcondition_breakdown(
        f_forged,
        expected_schema={"expected_values": {"C3": 999999}},
    )
    assert bd["format_valid"] is True
    assert bd["content_detected"] is True
    assert bd["task_requirement_satisfied"] is False
    assert bd["semantic_postcondition_passed"] is False
    assert bd["semantic_status"] == "unverified_formula"
    assert len(bd["unverified_formulas"]) == 1

    ok, _ = verify_artifact_postcondition(f_forged)
    assert ok is False


def test_p2_02_extended_supported_formulas_evaluate_accurately(tmp_path: Path):
    """Expanded safe formulas (ROUND, PRODUCT, COUNTA, ABS, arithmetic) evaluate deterministically."""
    f_ok = tmp_path / "extended_math.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Item", "Qty", "Price", "Subtotal"])
    ws.append(["A", 2, 150, "=B2*C2"])
    ws.append(["B", 3, 200, "=B3*C3"])
    ws["A4"] = "Total"
    ws["D4"] = "=SUM(D2:D3)"
    ws["D5"] = "=ROUND(AVERAGE(D2:D3), 0)"
    wb.save(str(f_ok))
    wb.close()

    ok, msg = verify_artifact_postcondition(
        f_ok,
        expected_schema={
            "require_formulas": True,
            "expected_values": {"D2": 300, "D3": 600, "D4": 900, "D5": 450},
        },
    )
    assert ok is True, msg


# ===========================================================================
# P2-03: Killable Subprocess Artifact Verifier Worker Actually Kills on Timeout
# ===========================================================================


@pytest.mark.asyncio
async def test_p2_03_worker_subprocess_kills_stalled_parser_process(monkeypatch, tmp_path: Path):
    """When parser stalls beyond timeout, verify_artifact_in_worker kills child PID immediately."""
    art = tmp_path / "sample.txt"
    art.write_text("Valid document text content.", encoding="utf-8")

    # Verify normal execution succeeds via real isolated subprocess
    ok_real, detail_real = await verify_artifact_in_worker(art, workspace=tmp_path, timeout=8.0)
    assert ok_real is True, detail_real

    # Spawn a real sleeping child process through create_subprocess_exec spy to assert hard OS kill on timeout
    spawned_pids: list[int] = []
    orig_exec = asyncio.create_subprocess_exec

    async def slow_worker_exec(*args, **kwargs):
        proc = await orig_exec(
            sys.executable,
            "-c",
            "import time; time.sleep(30)",
            stdin=kwargs.get("stdin"),
            stdout=kwargs.get("stdout"),
            stderr=kwargs.get("stderr"),
            start_new_session=kwargs.get("start_new_session", False),
        )
        spawned_pids.append(proc.pid)
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", slow_worker_exec)
    ok_to, msg_to = await verify_artifact_in_worker(art, workspace=tmp_path, timeout=0.25)
    assert ok_to is False
    assert "timeout" in msg_to.lower() or "dihentikan" in msg_to.lower()
    assert len(spawned_pids) == 1

    # Confirm child process is genuinely dead (reaped, no orphaned background thread lingering)
    if sys.platform != "win32":
        with pytest.raises(ProcessLookupError):
            os.kill(spawned_pids[0], 0)


# ===========================================================================
# P2-04: Replay API & Service Payload Bounds
# ===========================================================================


def test_p2_04_replay_budget_and_api_reject_oversized_fixtures(tmp_path: Path):
    """Oversized fixture arrays, input files, expected_artifacts, and HTTP payloads fail closed."""
    with pytest.raises(ValueError):
        validate_replay_fixtures_budget([{"name": f"f{i}"} for i in range(MAX_REPLAY_FIXTURES + 1)])

    with pytest.raises(ValueError):
        validate_replay_fixtures_budget(
            [{"name": "many_arts", "expected_artifacts": [f"a{i}.txt" for i in range(MAX_FIXTURE_EXPECTED_ARTIFACTS + 1)]}]
        )

    with pytest.raises(ValueError):
        validate_replay_fixtures_budget(
            [{"name": "many_inputs", "input_files": {f"in{i}.txt": "x" for i in range(MAX_FIXTURE_INPUT_FILES + 1)}}]
        )

    with pytest.raises(ValueError):
        validate_replay_fixtures_budget(
            [{"name": "huge_input", "input_files": {"big.txt": "A" * (MAX_FIXTURE_INPUT_FILE_BYTES + 10)}}]
        )

    agent_directory_service.set_root_dir(tmp_path / "aksa_data_p204")
    agent_id = "agent-c9-p204"
    skill_id = "cand-c9-p204"
    cand_dir = agent_directory_service.resolve_agent_path(agent_id, f"skills/candidates/{skill_id}")
    cand_dir.mkdir(parents=True, exist_ok=True)
    (cand_dir / "SKILL.md").write_text("---\nname: Budget Test\ndescription: Budget\n---\n# Budget\n", encoding="utf-8")

    app = create_app()
    with TestClient(app) as client:
        headers = {"X-AKSA-Auth-Token": settings.auth_token, "X-Principal-ID": get_default_host_principal()}
        resp = client.post(
            f"/api/v1/agents/{agent_id}/skills/{skill_id}/evaluate",
            headers=headers,
            json={
                "replay_fixtures": [
                    {
                        "name": "too_many_expected",
                        "expected_artifacts": [f"file_{i}.xlsx" for i in range(MAX_FIXTURE_EXPECTED_ARTIFACTS + 2)],
                    }
                ]
            },
        )
        assert resp.status_code == 400

        # Total HTTP body > MAX_TOTAL_REPLAY_PAYLOAD_BYTES + 65536 rejected immediately
        huge_payload = json.dumps({"replay_fixtures": [{"name": "huge", "inputs": {"blob": "B" * (MAX_TOTAL_REPLAY_PAYLOAD_BYTES + 100_000)}}]})
        resp_huge = client.post(
            f"/api/v1/agents/{agent_id}/skills/{skill_id}/evaluate",
            headers={**headers, "Content-Type": "application/json"},
            content=huge_payload,
        )
        assert resp_huge.status_code == 400


# ===========================================================================
# Section 6 #3: Pre-Parser OOXML ZIP Bomb & Dimension Guards
# ===========================================================================


def test_section6_office_zip_bomb_and_huge_sheet_dimension_rejected_before_openpyxl(
    monkeypatch, tmp_path: Path
):
    """Malicious ZIP ratio bombs and huge <dimension> ranges are rejected BEFORE openpyxl parses XML."""
    parser_invoked = []
    monkeypatch.setattr(
        openpyxl,
        "load_workbook",
        lambda *a, **kw: parser_invoked.append(True),
    )

    # 1. Tiny file expanding to huge zeroes (compression ratio bomb > 50:1 and > 512KB uncompressed)
    bomb_xlsx = tmp_path / "zip_bomb.xlsx"
    with zipfile.ZipFile(bomb_xlsx, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/sharedStrings.xml", b"0" * (2 * 1024 * 1024))
    assert bomb_xlsx.stat().st_size < 100 * 1024

    bd_bomb = get_artifact_postcondition_breakdown(bomb_xlsx)
    assert bd_bomb["format_valid"] is False
    assert bd_bomb["semantic_postcondition_passed"] is False
    assert "rasio kompresi" in bd_bomb["detail"].lower() or "melebihi batas" in bd_bomb["detail"].lower()
    assert parser_invoked == []

    # 2. Declared huge Excel sheet dimension <dimension ref="A1:XFD1048576"/>
    huge_dim_xlsx = tmp_path / "huge_dim.xlsx"
    with zipfile.ZipFile(huge_dim_xlsx, "w") as zf:
        zf.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet><dimension ref="A1:XFD1048576"/><sheetData/></worksheet>',
        )
    bd_dim = get_artifact_postcondition_breakdown(huge_dim_xlsx)
    assert bd_dim["format_valid"] is False
    assert bd_dim["semantic_postcondition_passed"] is False
    assert "dimensi" in bd_dim["detail"].lower()
    assert parser_invoked == []

