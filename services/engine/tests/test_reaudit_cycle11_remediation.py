"""Cycle 11 Re-Audit Remediation & Hardening Verification Suite.

Covers all findings and release gates from ``docs/AKSA-INDEPENDENT-REAUDIT-CYCLE-11-2026-11-19.md``:
- P1-01: Positive bounded RLIMIT_NPROC + single-threaded BLAS/OMP env so numpy/OpenBLAS works under
         Linux Bubblewrap & macOS Seatbelt while fork/subprocess spawning remains blocked.
- P2-01: DatabaseManager.ensure_ready() creates missing parent dirs & initializes schema before CRUD;
         curated skill installation test runs cleanly in isolated tmp_path without host AppData state.
- P2-02: Chained directory-FD opening (dir_fd + O_DIRECTORY | O_NOFOLLOW on POSIX; GetFinalPathNameByHandleW
         verification on Windows) eliminates TOCTOU intermediate-symlink swap races.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import openpyxl
import pytest

ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

import app.core.artifact_verifier as verifier_mod
import app.core.artifact_verifier_worker as worker_mod
import app.skills.os_sandbox as os_sandbox_mod
from app.core.agent_learning import SkillEvaluator
from app.core.artifact_verifier import get_artifact_postcondition_breakdown
from app.core.artifact_verifier_worker import verify_artifact_in_worker
from app.db.models import DatabaseManager
from app.skills.os_sandbox import collect_python_runtime_read_roots, execute_in_os_sandbox

has_real_os_sandbox = (
    sys.platform == "darwin"
    or (sys.platform.startswith("linux") and bool(shutil.which("bwrap")))
    or sys.platform == "win32"
)


# ===========================================================================
# P1-01: Positive RLIMIT_NPROC & OpenBLAS / numpy Compatibility Inside Sandbox
# ===========================================================================


@pytest.mark.asyncio
async def test_p1_01_verifier_worker_resource_limits_never_zero_nproc_and_compatible_with_numpy_openblas(
    monkeypatch, tmp_path: Path
):
    """RLIMIT_NPROC must remain strictly positive so numpy/OpenBLAS threads never fail EAGAIN."""
    ws = (tmp_path / "ws_openblas").resolve()
    ws.mkdir()
    xl = ws / "numpy_compat.xlsx"
    wb = openpyxl.Workbook()
    s = wb.active
    s.append(["Item", "Qty", "Price", "Total"])
    s.append(["Audit", 4, 250, "=B2*C2"])
    wb.save(str(xl))
    wb.close()

    captured_envs: list[dict[str, str]] = []
    orig_exec = os_sandbox_mod.execute_in_os_sandbox

    async def capture_env_exec(*args, **kwargs):
        captured_envs.append(dict(kwargs.get("env", {})))
        return await orig_exec(*args, **kwargs)

    monkeypatch.setattr(os_sandbox_mod, "execute_in_os_sandbox", capture_env_exec)

    ok, detail = await verify_artifact_in_worker(
        xl,
        expected_schema={"require_formulas": True, "expected_values": {"D2": 1000}},
        workspace=ws,
        timeout=12.0,
    )
    assert ok is True, detail
    assert len(captured_envs) == 1
    assert captured_envs[0].get("OPENBLAS_NUM_THREADS") == "1"
    assert captured_envs[0].get("OMP_NUM_THREADS") == "1"
    assert captured_envs[0].get("MALLOC_ARENA_MAX") == "2"

    # Execute numpy/OpenBLAS computation + worker resource limits & fork guards inside real OS sandbox
    if has_real_os_sandbox:
        req_roots, opt_roots = collect_python_runtime_read_roots()
        env_probe = dict(captured_envs[0])
        if sys.platform == "win32":
            env_probe["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
        probe_script = (
            "import mimetypes, sys; mimetypes.knownfiles = []; mimetypes.init()\n"
            "from app.core.artifact_verifier_worker import _apply_worker_resource_limits, _install_worker_process_guards\n"
            "_apply_worker_resource_limits(10.0)\n"
            "if sys.platform != 'win32':\n"
            "    import resource\n"
            "    soft_n, hard_n = resource.getrlimit(resource.RLIMIT_NPROC)\n"
            "    soft_f, hard_f = resource.getrlimit(resource.RLIMIT_FSIZE)\n"
            "    print('RLIMITS', soft_n, hard_n, soft_f, hard_f)\n"
            "_install_worker_process_guards()\n"
            "import numpy as np, openpyxl\n"
            "arr = np.dot(np.ones((4, 4)), np.ones((4, 4)))\n"
            "print('NUMPY_SUM', int(arr.sum()))\n"
            "try:\n"
            "    import subprocess; subprocess.run(['echo', 'hi'])\n"
            "    print('SUBPROC_ALLOWED')\n"
            "except Exception as e:\n"
            "    print('SUBPROC_BLOCKED', type(e).__name__)\n"
        )
        res = await execute_in_os_sandbox(
            cmd=[sys.executable, "-B", "-c", probe_script],
            cwd=ws,
            env=env_probe,
            workspace=ws,
            required_read_roots=req_roots,
            optional_read_roots=opt_roots,
            read_only_workspace=True,
            timeout=10.0,
        )
        assert res["exit_code"] == 0, res["stderr"]
        if sys.platform != "win32":
            r_line = [ln for ln in res["stdout"].splitlines() if ln.startswith("RLIMITS ")][0]
            _, s_n, h_n, s_f, h_f = r_line.split()
            assert int(s_n) > 0 and int(h_n) > 0, "RLIMIT_NPROC must remain strictly positive"
            assert int(s_f) == 0 and int(h_f) == 0, "RLIMIT_FSIZE must lock regular file writes to 0"
        assert "NUMPY_SUM 64" in res["stdout"]
        assert "SUBPROC_BLOCKED PermissionError" in res["stdout"]
        assert "SUBPROC_ALLOWED" not in res["stdout"]


@pytest.mark.asyncio
async def test_p1_01_skill_replay_xlsx_end_to_end_works_inside_os_sandbox(tmp_path: Path):
    """Regression check: SkillEvaluator full replay validating generated .xlsx passes under OS sandbox."""
    from app.core.agent_directory import agent_directory_service

    old_root = agent_directory_service.root_dir
    agent_directory_service.set_root_dir(tmp_path / "aksa_replay_root")
    try:
        md = "---\nname: Excel Summary\ndescription: Recap\n---\n# Recap\n"
        cand = {
            "skill_id": "cand-c11-xlsx",
            "structured_traces": [
                {
                    "step_id": "s1",
                    "tool_name": "excel_create_workbook",
                    "input_summary": {
                        "file_path": "rekap_c11.xlsx",
                        "sheets_spec": [
                            {
                                "title": "Rekap",
                                "headers": ["Bulan", "Nilai"],
                                "rows": [["Jan", 100], ["Feb", 200]],
                            }
                        ],
                    },
                    "status": "success",
                }
            ],
        }
        ev = await SkillEvaluator.replay_candidate_in_sandbox(
            md,
            "cand-c11-xlsx",
            cand,
            replay_fixtures=[
                {
                    "name": "basic_xlsx",
                    "expected_artifacts": ["rekap_c11.xlsx"],
                    "expected_schema": {"required_columns": ["Bulan", "Nilai"], "min_rows": 3},
                }
            ],
        )
        assert ev.passed is True, ev.replay_trace
        assert ev.replay_passed is True
    finally:
        agent_directory_service.set_root_dir(old_root)


# ===========================================================================
# P2-01: Uninitialized DatabaseManager Auto-Creates Parent Dirs & Schema
# ===========================================================================


@pytest.mark.asyncio
async def test_p2_01_database_manager_auto_creates_missing_parent_dir_and_schema_on_first_use(tmp_path: Path):
    """Fresh DB path whose parent directories do not exist yet must initialize seamlessly before upsert/audit."""
    fresh_path = tmp_path / "never_created" / "nested_data" / "aksa_fresh.db"
    assert not fresh_path.parent.exists()

    fresh_db = DatabaseManager(db_path=fresh_path)
    # Intentionally DO NOT call initialize() manually beforehand (reproduces CI fresh-runner scenario)
    row = await fresh_db.upsert_installed_skill({
        "skill_id": "indonesian-tax-calculator",
        "display_name": "Kalkulator PPh 21",
        "publisher": "AKSA Official",
        "installed_version": "1.0.0",
        "package_hash": "abc123",
        "trust_level": "curated",
        "enabled": False,
    })
    assert row["skill_id"] == "indonesian-tax-calculator"
    assert fresh_path.exists()

    aud = await fresh_db.log_permission_audit_event({
        "capability_id": "skill_installed_disabled",
        "resource_scope": "indonesian-tax-calculator",
        "decision": "allow",
        "reason_code": "INSTALL_DISABLED_BY_DEFAULT",
    })
    assert aud["capability_id"] == "skill_installed_disabled"


# ===========================================================================
# P2-02: Kernel-Atomic Directory-FD Traversal Closes Intermediate Symlink TOCTOU
# ===========================================================================


def test_p2_02_atomic_dir_fd_catches_intermediate_symlink_swap_after_preflight(monkeypatch, tmp_path: Path):
    """If an intermediate dir is swapped to a symlink AFTER preflight check, kernel dir_fd open still rejects it."""
    if sys.platform == "win32":
        pytest.skip("POSIX dir_fd O_DIRECTORY | O_NOFOLLOW test")

    outside_dir = (tmp_path / "outside_secret_dir").resolve()
    outside_sub = outside_dir / "nested"
    outside_sub.mkdir(parents=True)
    secret_file = outside_sub / "doc.txt"
    secret_file.write_text("CONFIDENTIAL_OUTSIDE_SWAP_LEAK", encoding="utf-8")

    ws = (tmp_path / "ws_race").resolve()
    real_mid = ws / "mid"
    real_nested = real_mid / "nested"
    real_nested.mkdir(parents=True)
    target = real_nested / "doc.txt"
    target.write_text("Legit safe content inside workspace.", encoding="utf-8")

    # Simulate an attacker swapping `ws/mid` -> `outside_dir` strictly AFTER preflight check passes
    # and right BEFORE `_open_verified_regular_fd` starts opening `dir_fd` segments.
    orig_anchor = verifier_mod._resolve_anchor_and_relative_parts

    def swap_mid_on_open(art_path: Path, workspace: Path | None = None):
        anchor, parts, err = orig_anchor(art_path, workspace=workspace)
        if anchor == ws and real_mid.exists() and not real_mid.is_symlink():
            shutil.rmtree(real_mid)
            real_mid.symlink_to(outside_dir, target_is_directory=True)
        return anchor, parts, err

    # Confirm preflight saw no symlinks first
    assert verifier_mod.check_no_symlink_components(target, workspace=ws) == (True, "")

    monkeypatch.setattr(verifier_mod, "_resolve_anchor_and_relative_parts", swap_mid_on_open)
    bd = get_artifact_postcondition_breakdown(
        target,
        expected_schema={"required_keywords": ["CONFIDENTIAL_OUTSIDE_SWAP_LEAK"]},
        workspace=ws,
    )
    assert bd["file_created"] is False
    assert bd["semantic_postcondition_passed"] is False
    assert "symlink" in bd["detail"].lower()


def test_p2_02_concurrent_intermediate_dir_symlink_swap_never_reads_outside_secret(tmp_path: Path):
    """Concurrent filesystem swap race loop must never read or validate outside secret bytes."""
    if sys.platform == "win32":
        pytest.skip("POSIX symlink race stress check")

    outside_dir = (tmp_path / "trap_outside").resolve()
    outside_dir.mkdir()
    (outside_dir / "target.txt").write_text("TRAP_SECRET_TOKEN_NEVER_READ", encoding="utf-8")

    ws = (tmp_path / "ws_concurrent_race").resolve()
    ws.mkdir()
    legit_dir = ws / "dir_backup"
    legit_dir.mkdir()
    (legit_dir / "target.txt").write_text("SAFE_LOCAL_TEXT_12345", encoding="utf-8")

    race_dir = ws / "race_slot"
    race_dir.mkdir()
    (race_dir / "target.txt").write_text("SAFE_LOCAL_TEXT_12345", encoding="utf-8")

    stop_event = threading.Event()

    def _flipper() -> None:
        toggle = False
        while not stop_event.is_set():
            tmp_swap = ws / "_swap_tmp"
            try:
                if tmp_swap.is_symlink() or tmp_swap.exists():
                    if tmp_swap.is_symlink():
                        tmp_swap.unlink()
                    else:
                        shutil.rmtree(tmp_swap, ignore_errors=True)
                if toggle:
                    tmp_swap.symlink_to(outside_dir, target_is_directory=True)
                else:
                    tmp_swap.mkdir(exist_ok=True)
                    (tmp_swap / "target.txt").write_text("SAFE_LOCAL_TEXT_12345", encoding="utf-8")

                if race_dir.is_symlink():
                    race_dir.unlink()
                elif race_dir.is_dir():
                    shutil.rmtree(race_dir, ignore_errors=True)
                tmp_swap.rename(race_dir)
            except OSError:
                pass
            toggle = not toggle
            time.sleep(0.001)

    t = threading.Thread(target=_flipper, daemon=True)
    t.start()
    try:
        candidate = race_dir / "target.txt"
        for _ in range(80):
            bd = get_artifact_postcondition_breakdown(
                candidate,
                expected_schema={"required_keywords": ["TRAP_SECRET_TOKEN_NEVER_READ"]},
                workspace=ws,
            )
            assert bd["semantic_postcondition_passed"] is False
    finally:
        stop_event.set()
        t.join(timeout=2)
