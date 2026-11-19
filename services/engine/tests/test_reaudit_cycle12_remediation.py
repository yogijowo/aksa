"""Cycle 12 Re-Audit Remediation & Packaging/Headroom Verification Suite.

Covers all findings and next-step priorities from ``docs/AKSA-INDEPENDENT-REAUDIT-CYCLE-12-2026-11-19.md``:
- P1-01 (CI / Packaging): Real PyInstaller sidecar build, explicit non-dummy binary & executable check,
                          and compiled binary smoke test MUST run before Cargo/Tauri checks in CI;
                          fail-closed rejection of missing or stub sidecar binaries.
- P2 (Residual RLIMIT_NPROC): Load-adaptive / configurable worker headroom + structured EAGAIN
                              telemetry and single adaptive bump retry on transient thread exhaustion.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ENGINE_ROOT = REPO_ROOT / "services" / "engine"
for _p in (str(ENGINE_ROOT), str(REPO_ROOT / "scripts"), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import app.core.artifact_verifier_worker as worker_mod
import app.skills.os_sandbox as os_sandbox_mod
from app.core.artifact_verifier_worker import (
    MAX_WORKER_MAX_NPROC_HEADROOM,
    _resolve_worker_nproc_headroom,
    verify_artifact_in_worker,
)
from build_sidecar import MIN_REAL_SIDECAR_BYTES, verify_sidecar_binary
from release_tooling import smoke_test_sidecar


# ===========================================================================
# P1-01: CI Builds & Verifies Real Sidecar Executable Before Cargo/Tauri
# ===========================================================================


def test_p1_01_ci_workflow_builds_and_verifies_real_sidecar_before_cargo():
    """CI workflow must freeze, verify non-stub, and smoke-test sidecar BEFORE cargo test/check."""
    ci_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    wf = yaml.safe_load(ci_path.read_text(encoding="utf-8"))
    steps = wf["jobs"]["backend-and-frontend"]["steps"]
    commands = [(s.get("name", ""), s.get("run", "")) for s in steps]

    idx_build = next(i for i, (_, r) in enumerate(commands) if "scripts/build_sidecar.py" in r and "--dry-run" not in r and "--verify-only" not in r)
    idx_verify = next(i for i, (_, r) in enumerate(commands) if "scripts/build_sidecar.py --verify-only" in r)
    idx_smoke_bin = next(i for i, (_, r) in enumerate(commands) if "smoke-test --require-executable" in r)
    idx_front_build = next(i for i, (_, r) in enumerate(commands) if "npm run build" in r)
    idx_cargo_test = next(i for i, (_, r) in enumerate(commands) if "cargo test" in r)
    idx_cargo_check = next(i for i, (_, r) in enumerate(commands) if "cargo check" in r)

    assert idx_build < idx_verify < idx_smoke_bin < idx_cargo_test < idx_cargo_check
    assert idx_front_build < idx_cargo_test
    # Ensure CI no longer skips real compilation with --dry-run only
    assert not any("--dry-run" in r for _, r in commands)


def test_p1_01_sidecar_verification_rejects_missing_symlinks_and_dummy_stubs(tmp_path: Path):
    """verify_sidecar_binary and --require-executable must fail closed on missing, symlink, or dummy binaries."""
    missing = tmp_path / "aksa-engine-missing"
    with pytest.raises(FileNotFoundError):
        verify_sidecar_binary(missing)
    assert smoke_test_sidecar(executable_path=missing, require_executable=True) is False

    # 270-byte shell wrapper / 0-byte dummy MUST be rejected fail-closed
    stub = tmp_path / "aksa-engine-stub"
    stub.write_text("#!/bin/sh\necho AKSA\n", encoding="utf-8")
    stub.chmod(0o755)
    with pytest.raises(RuntimeError):
        verify_sidecar_binary(stub, min_size_bytes=MIN_REAL_SIDECAR_BYTES)
    assert smoke_test_sidecar(executable_path=stub, require_executable=True) is False

    # Symlink sidecar must be rejected
    sym = tmp_path / "aksa-engine-sym"
    try:
        sym.symlink_to(stub)
    except OSError:
        pass
    else:
        with pytest.raises(FileNotFoundError):
            verify_sidecar_binary(sym)


def test_p1_01_pyproject_declares_numpy_and_pyinstaller():
    """pyproject.toml explicitly lists runtime numpy and dev PyInstaller dependencies."""
    content = (ENGINE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"numpy>=' in content
    assert '"pyinstaller>=' in content


# ===========================================================================
# P2: Adaptive RLIMIT_NPROC Headroom, EAGAIN Telemetry, & --verifier-worker CLI
# ===========================================================================


@pytest.mark.asyncio
async def test_p2_worker_adaptive_nproc_headroom_and_eagain_telemetry_retry(
    monkeypatch, caplog, tmp_path: Path
):
    """Adaptive RLIMIT_NPROC headroom scales cleanly and retries once with telemetry on EAGAIN."""
    monkeypatch.delenv("AKSA_VERIFIER_NPROC_HEADROOM", raising=False)
    assert _resolve_worker_nproc_headroom(20) == 64
    assert _resolve_worker_nproc_headroom(400) == 200
    assert _resolve_worker_nproc_headroom(5000) == MAX_WORKER_MAX_NPROC_HEADROOM

    monkeypatch.setenv("AKSA_VERIFIER_NPROC_HEADROOM", "120")
    assert _resolve_worker_nproc_headroom(20) == 120
    monkeypatch.setenv("AKSA_VERIFIER_NPROC_HEADROOM", "99999")
    assert _resolve_worker_nproc_headroom(20) == MAX_WORKER_MAX_NPROC_HEADROOM
    monkeypatch.delenv("AKSA_VERIFIER_NPROC_HEADROOM", raising=False)

    ws = (tmp_path / "ws_eagain").resolve()
    ws.mkdir()
    art = ws / "sample.txt"
    art.write_text("Valid artifact content for EAGAIN retry verification.", encoding="utf-8")

    # Simulate Linux UID baseline & transient OpenBLAS EAGAIN on attempt 1 -> adaptive retry succeeds
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(worker_mod, "_estimate_current_uid_tasks", lambda: 40)

    seen_limits: list[int] = []
    attempts = 0

    async def mock_exec(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        env = kwargs.get("env", {})
        seen_limits.append(int(env["AKSA_VERIFIER_MAX_NPROC"]))
        if attempts == 1:
            return {
                "exit_code": 130,
                "stdout": "",
                "stderr": "OpenBLAS blas_thread_init: pthread_create failed for thread 1: Resource temporarily unavailable (EAGAIN)",
            }
        return {
            "exit_code": 0,
            "stdout": json.dumps({"ok": True, "detail": "Valid"}),
            "stderr": "",
        }

    monkeypatch.setattr(os_sandbox_mod, "execute_in_os_sandbox", mock_exec)

    with caplog.at_level(logging.WARNING, logger="app.core.artifact_verifier_worker"):
        ok, detail = await verify_artifact_in_worker(art, workspace=ws, timeout=5.0)

    assert ok is True, detail
    assert attempts == 2
    assert len(seen_limits) == 2 and seen_limits[1] > seen_limits[0]
    assert any("verifier_worker.rlimit_nproc_eagain" in rec.message for rec in caplog.records)


def test_p2_main_verifier_worker_cli_roundtrip(tmp_path: Path):
    """python -m app.main --verifier-worker processes stdio payload cleanly for frozen sidecar parity."""
    ws = (tmp_path / "ws_cli").resolve()
    ws.mkdir()
    doc = ws / "ok.txt"
    doc.write_text("AKSA CLI verifier worker check.", encoding="utf-8")

    payload = json.dumps({
        "artifact_path": str(doc),
        "workspace": str(ws),
        "expected_schema": {},
    })
    res = subprocess.run(
        [sys.executable, "-m", "app.main", "--verifier-worker"],
        cwd=str(ENGINE_ROOT),
        input=payload,
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert res.returncode == 0, res.stderr
    parsed = json.loads(res.stdout)
    assert parsed["ok"] is True
    assert parsed["detail"] == "Valid"
