"""Cycle 13 Remediation & Hardening Verification Suite.

Covers all findings and requirements from ``docs/AKSA—Remediation Plan Siklus 13.md``:
- P2 (Adaptive RLIMIT_NPROC Retry): Deterministic fallback when UID task estimation returns None
  (/proc unavailable or unreadable), positive bounded limits within OS hard limits, genuine
  environment escalation on retry (no phantom retries), controlled failure at ceiling/2nd failure,
  and clear redacted telemetry.
- P2 (Linux Release Workflow): Official ``ubuntu-latest`` (``x86_64-unknown-linux-gnu``) pipeline in
  ``.github/workflows/release.yml`` with Bubblewrap runtime gate, native sidecar build/verification,
  Tauri ``deb``/``appimage`` bundle targets, SBOM, SHA-256 checksums, SLSA provenance, and artifact upload.
- P3 (Sidecar Binary Format & Arch Validation): Real ELF/Mach-O (thin & universal)/PE structural
  parsers matching target triples, rejecting wrong architectures, DLLs, Java class files, renamed text
  files, shell scripts, empty files, sub-1MB stubs, symlinks, and smoke-test failures cleanly.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import struct
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ENGINE_ROOT = REPO_ROOT / "services" / "engine"
for _p in (str(ENGINE_ROOT), str(REPO_ROOT / "scripts"), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import app.core.artifact_verifier_worker as worker_mod
import app.skills.os_sandbox as os_sandbox_mod
from build_sidecar import (
    MIN_REAL_SIDECAR_BYTES,
    parse_native_executable_header,
    validate_native_executable_format,
    verify_sidecar_binary,
)
from release_tooling import smoke_test_sidecar, verify_sidecar_binary_format


# ---------------------------------------------------------------------------
# Binary header builders for Section 4 structural tests (no external tools)
# ---------------------------------------------------------------------------


def _pad_to(buf: bytearray, total_size: int) -> bytes:
    if len(buf) < total_size:
        buf.extend(b"\x00" * (total_size - len(buf)))
    return bytes(buf)


def _make_elf64(machine: int, *, e_type: int = 3, size: int = MIN_REAL_SIDECAR_BYTES + 4096) -> bytes:
    buf = bytearray(128)
    buf[0:4] = b"\x7fELF"
    buf[4] = 2  # ELFCLASS64
    buf[5] = 1  # ELFDATA2LSB
    buf[6] = 1  # EV_CURRENT
    struct.pack_into(
        "<HHIQQQIHHHHHH",
        buf,
        16,
        e_type,   # e_type (ET_EXEC=2, ET_DYN=3)
        machine,  # e_machine (62=x86_64, 183=aarch64)
        1,        # e_version
        0x401000, # e_entry
        64,       # e_phoff
        0,        # e_shoff
        0,        # e_flags
        64,       # e_ehsize
        56,       # e_phentsize
        1,        # e_phnum
        64,       # e_shentsize
        0,        # e_shnum
        0,        # e_shstrndx
    )
    # Program header at offset 64: p_type=1 (PT_LOAD)
    struct.pack_into("<IIQQQQQQ", buf, 64, 1, 5, 0, 0x400000, 0x400000, 0x1000, 0x1000, 0x1000)
    return _pad_to(buf, size)


def _make_macho64(cputype: int, *, filetype: int = 2, size: int = MIN_REAL_SIDECAR_BYTES + 4096) -> bytes:
    buf = bytearray(128)
    struct.pack_into("<IiIIIIII", buf, 0, 0xFEEDFACF, cputype, 0, filetype, 1, 32, 0x200085, 0)
    return _pad_to(buf, size)


def _make_macho_universal(cputypes: list[int], *, size: int = MIN_REAL_SIDECAR_BYTES + 8192) -> bytes:
    buf = bytearray(size)
    nfat = len(cputypes)
    struct.pack_into(">II", buf, 0, 0xCAFEBABE, nfat)
    slice_offset = 4096
    slice_size = 4096
    for idx, cpu in enumerate(cputypes):
        off = slice_offset + idx * slice_size
        struct.pack_into(">iiIII", buf, 8 + idx * 20, cpu, 0, off, slice_size, 12)
        struct.pack_into("<IiIIIIII", buf, off, 0xFEEDFACF, cpu, 0, 2, 1, 32, 0x200085, 0)
    return bytes(buf)


def _make_pe64(
    machine: int,
    *,
    opt_magic: int = 0x020B,
    characteristics: int = 0x0022,
    size: int = MIN_REAL_SIDECAR_BYTES + 4096,
) -> bytes:
    buf = bytearray(max(size, 512))
    buf[0:2] = b"MZ"
    e_lfanew = 0x80
    struct.pack_into("<I", buf, 0x3C, e_lfanew)
    buf[e_lfanew : e_lfanew + 4] = b"PE\x00\x00"
    opt_size = 240 if opt_magic == 0x020B else 224
    struct.pack_into("<HHIIIHH", buf, e_lfanew + 4, machine, 1, 0, 0, 0, opt_size, characteristics)
    struct.pack_into("<H", buf, e_lfanew + 24, opt_magic)
    return bytes(buf)


# ===========================================================================
# 1. Section 2 (P2): Adaptive RLIMIT_NPROC Fallback, Retry & Hard-Limit Bounds
# ===========================================================================


def test_s13_p2_uid_task_estimation_handles_success_missing_and_unreadable_proc(monkeypatch):
    """_estimate_current_uid_tasks works on valid /proc and fails safe to None if /proc missing/unreadable."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(os, "getuid", lambda: 1000)

    # 1. Successful estimation across multiple UIDs
    fake_entries = [SimpleNamespace(name="101"), SimpleNamespace(name="202"), SimpleNamespace(name="self")]
    monkeypatch.setattr(os, "scandir", lambda path: iter(fake_entries))

    fake_status = {
        "/proc/101/status": "Name:\tpython\nUid:\t1000\t1000\t1000\t1000\nThreads:\t7\n",
        "/proc/202/status": "Name:\troot_proc\nUid:\t0\t0\t0\t0\nThreads:\t3\n",
    }

    class _FakeFile:
        def __init__(self, text: str) -> None:
            self._lines = text.splitlines(keepends=True)

        def __enter__(self):
            return iter(self._lines)

        def __exit__(self, *args):
            return False

    orig_open = open

    def mock_open(path, *args, **kwargs):
        if str(path) in fake_status:
            return _FakeFile(fake_status[str(path)])
        return orig_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", mock_open)
    assert worker_mod._estimate_current_uid_tasks() == 7

    # 2. /proc unavailable -> None
    monkeypatch.setattr(os, "scandir", lambda path: (_ for _ in ()).throw(FileNotFoundError("/proc missing")))
    assert worker_mod._estimate_current_uid_tasks() is None

    # 3. /proc unreadable -> None
    monkeypatch.setattr(os, "scandir", lambda path: (_ for _ in ()).throw(PermissionError("permission denied")))
    assert worker_mod._estimate_current_uid_tasks() is None

    # 4. Initial limit calculation never drops to zero even when uid_tasks=None
    monkeypatch.delenv("AKSA_VERIFIER_NPROC_HEADROOM", raising=False)
    headroom = worker_mod._resolve_worker_nproc_headroom(None)
    limit_fallback, source_fb = worker_mod._compute_initial_worker_nproc_limit(None, headroom, hard_limit=None)
    assert source_fb == "deterministic_fallback"
    assert limit_fallback == worker_mod.DEFAULT_WORKER_FALLBACK_UID_TASKS + headroom
    assert limit_fallback >= worker_mod.MIN_WORKER_MAX_NPROC > 0


@pytest.mark.asyncio
async def test_s13_p2_eagain_retry_with_uid_tasks_none_escalates_env_and_succeeds(
    monkeypatch, caplog, tmp_path: Path
):
    """When /proc estimation returns None, initial fallback & EAGAIN retry genuinely escalate AKSA_VERIFIER_MAX_NPROC."""
    monkeypatch.delenv("AKSA_VERIFIER_NPROC_HEADROOM", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(worker_mod, "_estimate_current_uid_tasks", lambda: None)
    monkeypatch.setattr(worker_mod, "_resolve_system_nproc_hard_limit", lambda: 2048)

    ws = (tmp_path / "ws_none_retry").resolve()
    ws.mkdir()
    art = ws / "report.txt"
    art.write_text("AKSA Cycle 13 valid document content.", encoding="utf-8")

    seen_nproc_env: list[int] = []

    async def mock_exec(*args, **kwargs):
        env = kwargs.get("env", {})
        assert "AKSA_VERIFIER_MAX_NPROC" in env, "AKSA_VERIFIER_MAX_NPROC must ALWAYS be set even if uid_tasks is None"
        val = int(env["AKSA_VERIFIER_MAX_NPROC"])
        assert val >= worker_mod.MIN_WORKER_MAX_NPROC > 0
        seen_nproc_env.append(val)
        if len(seen_nproc_env) == 1:
            return {
                "exit_code": 130,
                "stdout": "",
                "stderr": "OpenBLAS blas_thread_init: pthread_create failed: Resource temporarily unavailable",
            }
        return {
            "exit_code": 0,
            "stdout": json.dumps({"ok": True, "detail": "Valid"}),
            "stderr": "",
        }

    monkeypatch.setattr(os_sandbox_mod, "execute_in_os_sandbox", mock_exec)

    with caplog.at_level(logging.WARNING, logger="app.core.artifact_verifier_worker"):
        ok, detail = await worker_mod.verify_artifact_in_worker(art, workspace=ws, timeout=5.0)

    assert ok is True, detail
    assert len(seen_nproc_env) == 2
    assert seen_nproc_env[0] >= worker_mod.MIN_WORKER_MAX_NPROC
    assert seen_nproc_env[1] > seen_nproc_env[0]
    assert seen_nproc_env[1] <= 2048
    logs = "\n".join(r.message for r in caplog.records)
    assert "verifier_worker.rlimit_nproc_eagain" in logs
    assert "verifier_worker.rlimit_nproc_retrying" in logs
    assert str(ws) not in logs  # Telemetry must not leak workspace paths


@pytest.mark.asyncio
async def test_s13_p2_second_attempt_still_failing_returns_controlled_error(
    monkeypatch, caplog, tmp_path: Path
):
    """When both attempt 1 and retry attempt 2 fail with EAGAIN, worker returns controlled failure + telemetry."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(worker_mod, "_estimate_current_uid_tasks", lambda: None)
    monkeypatch.setattr(worker_mod, "_resolve_system_nproc_hard_limit", lambda: 2048)

    ws = (tmp_path / "ws_both_fail").resolve()
    ws.mkdir()
    art = ws / "doc.txt"
    art.write_text("AKSA Cycle 13 content.", encoding="utf-8")

    seen_nproc_env: list[int] = []

    async def mock_exec_fail(*args, **kwargs):
        seen_nproc_env.append(int(kwargs["env"]["AKSA_VERIFIER_MAX_NPROC"]))
        return {
            "exit_code": 1,
            "stdout": "",
            "stderr": "pthread_create failed: Resource temporarily unavailable (EAGAIN)",
        }

    monkeypatch.setattr(os_sandbox_mod, "execute_in_os_sandbox", mock_exec_fail)

    with caplog.at_level(logging.WARNING, logger="app.core.artifact_verifier_worker"):
        ok, detail = await worker_mod.verify_artifact_in_worker(art, workspace=ws, timeout=5.0)

    assert ok is False
    assert "gagal" in detail.lower()
    assert len(seen_nproc_env) == 2
    assert seen_nproc_env[1] > seen_nproc_env[0]
    logs = "\n".join(r.message for r in caplog.records)
    assert "verifier_worker.rlimit_nproc_exhausted" in logs


@pytest.mark.asyncio
async def test_s13_p2_nproc_never_exceeds_hard_limit_or_runs_phantom_retry_at_ceiling(
    monkeypatch, caplog, tmp_path: Path
):
    """RLIMIT_NPROC never exceeds OS hard limit, never sets 0, and blocks phantom retry if already at ceiling."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(worker_mod, "_estimate_current_uid_tasks", lambda: None)
    # Tight OS hard limit equal to initial deterministic fallback (128)
    monkeypatch.setattr(worker_mod, "_resolve_system_nproc_hard_limit", lambda: 128)

    ws = (tmp_path / "ws_ceiling").resolve()
    ws.mkdir()
    art = ws / "doc.txt"
    art.write_text("AKSA Cycle 13 ceiling check.", encoding="utf-8")

    calls = 0

    async def mock_exec_ceiling(*args, **kwargs):
        nonlocal calls
        calls += 1
        assert int(kwargs["env"]["AKSA_VERIFIER_MAX_NPROC"]) == 128
        return {
            "exit_code": 130,
            "stdout": "",
            "stderr": "Resource temporarily unavailable",
        }

    monkeypatch.setattr(os_sandbox_mod, "execute_in_os_sandbox", mock_exec_ceiling)

    with caplog.at_level(logging.WARNING, logger="app.core.artifact_verifier_worker"):
        ok, detail = await worker_mod.verify_artifact_in_worker(art, workspace=ws, timeout=5.0)

    assert ok is False
    assert calls == 1  # No phantom second retry when limit cannot increase!
    assert "batas" in detail.lower() or "rlimit_nproc" in detail.lower()
    assert any("verifier_worker.rlimit_nproc_retry_blocked" in r.message for r in caplog.records)

    # Also verify _apply_worker_resource_limits refuses "0" and invalid values
    if sys.platform != "win32":
        import resource

        recorded_nproc: list[tuple[int, int]] = []
        orig_setrlimit = resource.setrlimit
        orig_getrlimit = resource.getrlimit

        def fake_getrlimit(rsrc):
            if rsrc == resource.RLIMIT_NPROC:
                return (64, 150)
            return orig_getrlimit(rsrc)

        def fake_setrlimit(rsrc, limits):
            if rsrc == resource.RLIMIT_NPROC:
                recorded_nproc.append(limits)
            return None

        monkeypatch.setattr(resource, "getrlimit", fake_getrlimit)
        monkeypatch.setattr(resource, "setrlimit", fake_setrlimit)
        monkeypatch.setenv("AKSA_VERIFIER_MAX_NPROC", "0")
        worker_mod._apply_worker_resource_limits(timeout_sec=10.0)
        assert recorded_nproc and recorded_nproc[-1] == (64, 64)

        monkeypatch.setenv("AKSA_VERIFIER_MAX_NPROC", "9999")
        worker_mod._apply_worker_resource_limits(timeout_sec=10.0)
        assert recorded_nproc[-1] == (150, 150)  # Clamped strictly to hard limit 150!


# ===========================================================================
# 2. Section 3 (P2): Official Linux Release Pipeline & Tauri Targets
# ===========================================================================


def test_s13_p2_release_workflow_and_tauri_conf_support_linux_end_to_end():
    """release.yml includes full ubuntu-latest x86_64-unknown-linux-gnu pipeline & tauri.conf.json enables deb/appimage."""
    rel_path = REPO_ROOT / ".github" / "workflows" / "release.yml"
    wf = yaml.safe_load(rel_path.read_text(encoding="utf-8"))
    job = wf["jobs"]["build-and-release"]
    includes = job["strategy"]["matrix"]["include"]

    linux_entries = [m for m in includes if m["os"] == "ubuntu-latest"]
    assert len(linux_entries) == 1
    assert linux_entries[0]["triple"] == "x86_64-unknown-linux-gnu"
    assert linux_entries[0]["ext"] == ""

    steps = job["steps"]
    runs = "\n".join(s.get("run", "") for s in steps)
    assert "bubblewrap" in runs and "libwebkit2gtk-4.1-dev" in runs
    assert "test_real_linux_bwrap_isolates_home_and_network" in runs
    assert "scripts/build_sidecar.py --triple ${{ matrix.triple }}" in runs
    assert "scripts/build_sidecar.py --verify-only --triple ${{ matrix.triple }}" in runs
    assert "scripts/release_tooling.py verify-binary" in runs
    assert "scripts/release_tooling.py smoke-test" in runs and "--require-executable" in runs
    assert "npx tsc --noEmit" in runs
    assert "npm run build" in runs
    assert "npm run test" in runs
    assert "cargo test" in runs
    assert "npx tauri build" in runs
    assert "release_tooling.py sbom" in runs
    assert "release_tooling.py verify-checksums" in runs

    # Fail-closed dist preparation: no '|| true' swallowing missing installers
    prep_step = next(s for s in steps if "Dist Directory" in s["name"])
    assert "|| true" not in prep_step["run"]
    assert "Zero Tauri installer packages" in prep_step["run"]

    # Every uses: action must stay commit-SHA pinned (not floating branch/tag)
    for step in steps:
        if "uses" in step:
            ref = step["uses"].split("#", 1)[0].strip()
            sha = ref.split("@", 1)[1]
            assert re.fullmatch(r"[0-9a-f]{40}", sha), f"Action not pinned to 40-char SHA: {step['uses']}"

    # Artifact upload step must exist
    assert any(s.get("uses", "").startswith("actions/upload-artifact@") for s in steps)

    # Tauri config declares Linux bundle targets cleanly
    tauri_conf = json.loads((REPO_ROOT / "apps" / "desktop" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    targets = tauri_conf["bundle"]["targets"]
    for req_target in ("nsis", "msi", "dmg", "app", "deb", "appimage"):
        assert req_target in targets


# ===========================================================================
# 3. Section 4 (P3): Structural Sidecar Binary Format & Arch Validation
# ===========================================================================


def test_s13_p3_valid_elf_macho_universal_and_pe_binaries_pass(tmp_path: Path):
    """Valid ELF, thin Mach-O, Universal Fat Mach-O, and PE32+ executables pass matching triple validation."""
    elf_x64 = tmp_path / "aksa-engine-x86_64-unknown-linux-gnu"
    elf_x64.write_bytes(_make_elf64(62, e_type=3))  # PIE ET_DYN
    elf_x64.chmod(0o755)
    info_elf = validate_native_executable_format(elf_x64, expected_triple="x86_64-unknown-linux-gnu")
    assert info_elf["format"] == "elf" and info_elf["arch"] == "x86_64"

    elf_arm = tmp_path / "aksa-engine-aarch64-unknown-linux-gnu"
    elf_arm.write_bytes(_make_elf64(183, e_type=2))  # ET_EXEC
    elf_arm.chmod(0o755)
    info_elf_arm = validate_native_executable_format(elf_arm, expected_triple="aarch64-unknown-linux-gnu")
    assert info_elf_arm["format"] == "elf" and info_elf_arm["arch"] == "arm64"

    macho_arm = tmp_path / "aksa-engine-aarch64-apple-darwin"
    macho_arm.write_bytes(_make_macho64(0x0100000C))
    macho_arm.chmod(0o755)
    info_mac = verify_sidecar_binary_format(macho_arm, expected_triple="aarch64-apple-darwin")
    assert info_mac["format"] == "macho" and info_mac["arch"] == "arm64"

    macho_uni = tmp_path / "aksa-universal"
    macho_uni.write_bytes(_make_macho_universal([0x0100000C, 0x01000007]))
    macho_uni.chmod(0o755)
    assert validate_native_executable_format(macho_uni, expected_triple="aarch64-apple-darwin")["universal"] is True
    assert validate_native_executable_format(macho_uni, expected_triple="x86_64-apple-darwin")["universal"] is True

    pe_x64 = tmp_path / "aksa-engine-x86_64-pc-windows-msvc.exe"
    pe_x64.write_bytes(_make_pe64(0x8664))
    info_pe = validate_native_executable_format(pe_x64, expected_triple="x86_64-pc-windows-msvc")
    assert info_pe["format"] == "pe" and info_pe["arch"] == "x86_64"

    # If host macOS binary exists locally, validate the genuine PyInstaller artifact as well
    real_mac = REPO_ROOT / "apps" / "desktop" / "src-tauri" / "binaries" / "aksa-engine-aarch64-apple-darwin"
    if real_mac.exists():
        real_info = verify_sidecar_binary(real_mac, expected_triple="aarch64-apple-darwin")
        assert real_info == real_mac


def test_s13_p3_rejects_wrong_arch_wrong_format_text_script_empty_tiny_and_symlink(tmp_path: Path):
    """Format parser & verify_sidecar_binary reject wrong arch, cross-OS format, DLL, text, shell, empty, stub, and symlink."""
    # 1. Wrong architecture (ARM64 ELF checked as x86_64-unknown-linux-gnu)
    wrong_arch_elf = tmp_path / "aksa-arm-elf"
    wrong_arch_elf.write_bytes(_make_elf64(183))
    wrong_arch_elf.chmod(0o755)
    with pytest.raises(RuntimeError, match="Arsitektur"):
        validate_native_executable_format(wrong_arch_elf, expected_triple="x86_64-unknown-linux-gnu")

    # 2. Wrong OS binary (Linux ELF masquerading on macOS target)
    with pytest.raises(RuntimeError, match="Format binary"):
        validate_native_executable_format(wrong_arch_elf, expected_triple="aarch64-apple-darwin")

    # 3. Wrong Mach-O arch (x86_64 Mach-O checked as arm64) & wrong filetype (MH_DYLIB=6)
    mac_x64 = tmp_path / "aksa-mac-x64"
    mac_x64.write_bytes(_make_macho64(0x01000007))
    mac_x64.chmod(0o755)
    with pytest.raises(RuntimeError, match="Arsitektur"):
        validate_native_executable_format(mac_x64, expected_triple="aarch64-apple-darwin")

    mac_dylib = tmp_path / "aksa-mac-dylib"
    mac_dylib.write_bytes(_make_macho64(0x0100000C, filetype=6))
    with pytest.raises(RuntimeError, match="MH_EXECUTE"):
        parse_native_executable_header(mac_dylib)

    # 4. PE 32-bit x86 / PE DLL masquerading as x86_64 Windows executable
    pe_x86 = tmp_path / "aksa-x86.exe"
    pe_x86.write_bytes(_make_pe64(0x014C, opt_magic=0x010B))
    with pytest.raises(RuntimeError):
        validate_native_executable_format(pe_x86, expected_triple="x86_64-pc-windows-msvc")

    pe_dll = tmp_path / "aksa-dll.exe"
    pe_dll.write_bytes(_make_pe64(0x8664, characteristics=0x2002))  # IMAGE_FILE_DLL set
    with pytest.raises(RuntimeError, match="DLL"):
        validate_native_executable_format(pe_dll, expected_triple="x86_64-pc-windows-msvc")

    # 5. Plain text file renamed with .exe extension & > 1MB size
    text_exe = tmp_path / "fake.exe"
    text_exe.write_bytes(b"Not a native PE binary\n" * 60_000)
    assert smoke_test_sidecar(executable_path=text_exe, require_executable=True, expected_triple="x86_64-pc-windows-msvc") is False

    # 6. Shell script masquerading as binary > 1MB size
    sh_bin = tmp_path / "fake-linux"
    sh_bin.write_bytes(b"#!/bin/sh\necho 'AKSA Engine v1.0.0'\n" + (b"# pad\n" * 200_000))
    sh_bin.chmod(0o755)
    assert smoke_test_sidecar(executable_path=sh_bin, require_executable=True, expected_triple="x86_64-unknown-linux-gnu") is False

    # 7. Empty 0-byte file
    empty_bin = tmp_path / "empty-bin"
    empty_bin.write_bytes(b"")
    with pytest.raises(RuntimeError):
        verify_sidecar_binary(empty_bin, expected_triple="x86_64-unknown-linux-gnu")

    # 8. Valid native header below minimum 1 MB size (stub)
    tiny_elf = tmp_path / "tiny-elf"
    tiny_elf.write_bytes(_make_elf64(62, size=512))
    tiny_elf.chmod(0o755)
    with pytest.raises(RuntimeError, match="terlalu kecil"):
        verify_sidecar_binary(tiny_elf, expected_triple="x86_64-unknown-linux-gnu")

    # 9. Symlink to valid binary rejected
    sym_bin = tmp_path / "sym-elf"
    try:
        sym_bin.symlink_to(mac_x64)
    except OSError:
        pass
    else:
        with pytest.raises(FileNotFoundError):
            verify_sidecar_binary(sym_bin, expected_triple="x86_64-apple-darwin")


def test_s13_p3_valid_binary_failing_behavioral_smoke_test_is_rejected(monkeypatch, tmp_path: Path):
    """Even with valid ELF/Mach-O/PE format & size, failing --version or --smoke-test causes smoke_test_sidecar to fail closed."""
    triple = "x86_64-unknown-linux-gnu"
    valid_bin = tmp_path / "aksa-engine-x86_64-unknown-linux-gnu"
    valid_bin.write_bytes(_make_elf64(62))
    valid_bin.chmod(0o755)

    import subprocess as sp

    def fail_smoke(cmd, *args, **kwargs):
        if "--version" in cmd:
            return sp.CompletedProcess(cmd, 0, stdout="AKSA Engine v1.0.0 (API v1)\n", stderr="")
        return sp.CompletedProcess(cmd, 1, stdout="", stderr="subsystem initialization crashed")

    monkeypatch.setattr(sp, "run", fail_smoke)
    assert smoke_test_sidecar(executable_path=valid_bin, require_executable=True, expected_triple=triple) is False
