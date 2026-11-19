"""Cycle 10 Re-Audit Remediation & Hardening Verification Suite.

Covers all findings and hardening priorities from ``docs/AKSA-INDEPENDENT-REAUDIT-CYCLE-10-2026-11-19.md``:
- P2-01: Artifact verifier worker runs inside the OS-enforced sandbox (Seatbelt / Bubblewrap /
         AppContainer) with a READ-ONLY workspace, ZERO network access, minimal runtime roots,
         and defense-in-depth resource/process limits.
- P2-02: Streaming bounded stdout/stderr reader in both OS sandbox & verifier worker aborts and
         kills the child process group immediately when hard caps are breached (never buffers full
         flood output via ``proc.communicate()``) and keeps only a short diagnostic stderr snippet.
- Hardening: Standalone pure-Python ``app.core.artifact_verifier`` (no server/DB/LLM imports)
         and atomic ``O_NOFOLLOW`` + intermediate symlink checks to close TOCTOU path races.
"""

from __future__ import annotations

import ast
import asyncio
import ctypes
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import openpyxl
import pymupdf as fitz
import pytest

ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

import app.core.artifact_verifier_worker as worker_mod
import app.skills.os_sandbox as os_sandbox_mod
from app.core.artifact_verifier import (
    get_artifact_postcondition_breakdown,
)
from app.core.artifact_verifier_worker import verify_artifact_in_worker
from app.skills.os_sandbox import (
    SandboxOutputLimitError,
    build_linux_bwrap_args,
    build_seatbelt_profile,
    collect_python_runtime_read_roots,
    execute_in_os_sandbox,
)
from app.skills.windows_sandbox import run_windows_appcontainer_sandboxed

has_real_os_sandbox = (
    sys.platform == "darwin"
    or (sys.platform.startswith("linux") and bool(shutil.which("bwrap")))
    or sys.platform == "win32"
)
real_sandbox_only = pytest.mark.skipif(
    not has_real_os_sandbox,
    reason="Real OS sandbox runtime test",
)


# ===========================================================================
# P2-01: Verifier Worker Runs Under OS Security Sandbox (Read-Only + No Net)
# ===========================================================================


@pytest.mark.asyncio
async def test_p2_01_verifier_worker_invokes_os_sandbox_with_readonly_workspace_and_streaming_limits(
    monkeypatch, tmp_path: Path
):
    """verify_artifact_in_worker MUST delegate execution to OS sandbox with read_only_workspace=True & hard caps."""
    ws = tmp_path / "ws"
    ws.mkdir()

    # Build real valid .xlsx and .pdf artifacts
    xl = ws / "report.xlsx"
    wb = openpyxl.Workbook()
    sheet = wb.active
    sheet.append(["Item", "Qty", "Price", "Total"])
    sheet.append(["A", 2, 50, "=B2*C2"])
    wb.save(str(xl))
    wb.close()

    pdf = ws / "summary.pdf"
    doc = fitz.open()
    pg = doc.new_page()
    pg.insert_text((72, 72), "Laporan Audit Keamanan AKSA Siklus 10 Verified.")
    pdf.write_bytes(doc.tobytes())
    doc.close()

    captured_calls: list[dict[str, Any]] = []
    orig_exec = os_sandbox_mod.execute_in_os_sandbox

    async def spy_os_sandbox(*args, **kwargs):
        captured_calls.append({"args": args, "kwargs": dict(kwargs)})
        return await orig_exec(*args, **kwargs)

    monkeypatch.setattr(os_sandbox_mod, "execute_in_os_sandbox", spy_os_sandbox)

    ok_xl, msg_xl = await verify_artifact_in_worker(
        xl,
        expected_schema={"expected_values": {"D2": 100}},
        workspace=ws,
        timeout=12.0,
    )
    assert ok_xl is True, msg_xl

    ok_pdf, msg_pdf = await verify_artifact_in_worker(
        pdf,
        expected_schema={"required_keywords": ["Siklus 10"]},
        workspace=ws,
        timeout=12.0,
    )
    assert ok_pdf is True, msg_pdf

    assert len(captured_calls) == 2
    for call in captured_calls:
        kw = call["kwargs"]
        assert kw["read_only_workspace"] is True
        assert kw["abort_on_output_limit"] is True
        assert kw["max_output_bytes"] == worker_mod.MAX_WORKER_STDOUT_BYTES
        assert kw["max_stderr_bytes"] == worker_mod.MAX_WORKER_STDERR_BYTES
        assert kw["stderr_retain_bytes"] == worker_mod.MAX_WORKER_STDERR_SNIPPET_BYTES
        assert isinstance(kw["stdin_bytes"], (bytes, bytearray))
        # Scrubbed env MUST NOT pass host HOME or unrelated env vars
        child_env = kw["env"]
        assert child_env.get("PYTHONDONTWRITEBYTECODE") == "1"
        assert child_env.get("PYTHONNOUSERSITE") == "1"
        if sys.platform != "win32":
            assert child_env.get("HOME") == str(ws.resolve())


def test_p2_01_os_sandbox_profiles_enforce_readonly_workspace_across_all_platforms(monkeypatch, tmp_path: Path):
    """macOS Seatbelt, Linux Bubblewrap, and Windows AppContainer profiles all restrict workspace to read-only."""
    ws = tmp_path / "ro_ws"
    ws.mkdir()

    # 1. macOS Seatbelt: NO (subpath ws) write rule when read_only_workspace=True
    seatbelt = build_seatbelt_profile(ws, [ENGINE_ROOT, ws], read_only_workspace=True)
    assert "(deny default)" in seatbelt
    assert "(deny network*)" in seatbelt
    assert "(deny process-fork)" in seatbelt
    write_section = seatbelt.split("(allow file-write*", 1)[1]
    assert str(ws.resolve()) not in write_section
    assert '(literal "/dev/null")' in write_section

    # 2. Linux Bubblewrap: uses --ro-bind for ws AND --remount-ro /, never --bind for ws
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/bwrap" if name == "bwrap" else None)
    bwrap_args = build_linux_bwrap_args(ws, [ENGINE_ROOT], [sys.executable, "-V"], read_only_workspace=True)
    ws_str = str(ws.resolve())
    idx_ro = bwrap_args.index("--ro-bind")
    assert bwrap_args[idx_ro + 1 : idx_ro + 3] == [ws_str, ws_str]
    assert "--bind" not in bwrap_args
    assert "--remount-ro" in bwrap_args
    assert "--tmpfs" not in bwrap_args

    # 3. Windows AppContainer: grants FILE_READ_EXEC (0x001200A9) rather than FILE_ALL_ACCESS (0x001F01FF)
    #    and configures 3 handles (h_in_r, h_out_w, h_err_w) in HANDLE_LIST when stdin_bytes is provided.
    acl_grants: list[tuple[int, int]] = []
    handle_lists: list[list[int]] = []

    class FakeWintypes:
        DWORD = ctypes.c_uint32
        ULONG = ctypes.c_uint32
        UINT = ctypes.c_uint32
        BOOL = ctypes.c_int
        WORD = ctypes.c_uint16
        HANDLE = ctypes.c_void_p
        LPCWSTR = ctypes.c_wchar_p
        LPWSTR = ctypes.c_wchar_p

    next_pipe = 0x2000

    class FakeDLL:
        def __init__(self, name: str):
            self.name = name

        def __getattr__(self, fn_name: str):
            def _fn(*args):
                nonlocal next_pipe
                if fn_name in ("CreateAppContainerProfile", "GetNamedSecurityInfoW"):
                    return 0
                if fn_name == "SetEntriesInAclW":
                    ea = args[1]._obj
                    acl_grants.append((int(ea.grfAccessMode), int(ea.grfAccessPermissions)))
                    return 0
                if fn_name == "SetNamedSecurityInfoW":
                    return 0
                if fn_name == "CreatePipe":
                    r_v, w_v = next_pipe, next_pipe + 4
                    next_pipe += 0x10
                    ctypes.cast(args[0], ctypes.POINTER(ctypes.c_void_p))[0] = r_v
                    ctypes.cast(args[1], ctypes.POINTER(ctypes.c_void_p))[0] = w_v
                    return 1
                if fn_name == "UpdateProcThreadAttribute" and int(args[2]) == 0x00020002:
                    handle_lists.append(list(args[3]))
                    return 1
                if fn_name == "CreateJobObjectW":
                    return 777
                if fn_name == "AssignProcessToJobObject":
                    return 0  # Fail safely BEFORE ResumeThread so no real handles/threads are created
                if fn_name in (
                    "SetInformationJobObject",
                    "InitializeProcThreadAttributeList",
                    "UpdateProcThreadAttribute",
                    "SetHandleInformation",
                    "CreateProcessW",
                    "TerminateProcess",
                    "CloseHandle",
                    "DeleteAppContainerProfile",
                    "FreeSid",
                ):
                    return 1
                return 0

            return _fn

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(ctypes, "WinDLL", lambda name, **kw: FakeDLL(name), raising=False)
    monkeypatch.setattr(ctypes, "wintypes", FakeWintypes, raising=False)

    ro_extra = tmp_path / "extra_ro"
    ro_extra.mkdir()
    with pytest.raises(PermissionError):
        run_windows_appcontainer_sandboxed(
            cmd=["python.exe", "-m", "app.core.artifact_verifier_worker"],
            cwd=ws,
            env={"PATH": ""},
            workspace=ws,
            required_read_roots=[ro_extra],
            stdin_bytes=b'{"test":1}',
            read_only_workspace=True,
        )

    grants_only = [perm for mode, perm in acl_grants if mode == 1]
    assert grants_only, "AppContainer ACL setup should have granted ACLs"
    # Every GRANT_ACCESS entry MUST be FILE_READ_EXEC (0x001200A9), NOT FILE_ALL_ACCESS
    assert grants_only[0] == 0x001200A9
    assert all(mask == 0x001200A9 for mask in grants_only)
    assert len(handle_lists) == 1 and len(handle_lists[0]) == 3


@real_sandbox_only
@pytest.mark.asyncio
async def test_p2_01_verifier_real_sandbox_blocks_write_network_and_outside_access(tmp_path: Path):
    """Real OS runtime check: read_only_workspace=True allows reading ws artifact while denying writes, network, and host escape."""
    ws = (tmp_path / "ws").resolve()
    ws.mkdir()
    legit = ws / "legit.txt"
    legit.write_text("SAFE_ARTIFACT_BYTES", encoding="utf-8")

    outside_secret = tmp_path / "host_secret.txt"
    outside_secret.write_text("SUPER_SECRET_HOST", encoding="utf-8")
    outside_write = tmp_path / "escape_write.txt"
    tamper_ws = ws / "tamper.txt"

    req_roots, opt_roots = collect_python_runtime_read_roots()
    probe_code = f"""
import pathlib, socket
try:
    txt = pathlib.Path(r'{legit}').read_text(encoding='utf-8')
    print('READ_WS', 'OK' if txt == 'SAFE_ARTIFACT_BYTES' else 'MISMATCH')
except Exception as e:
    print('READ_WS', 'ERR', type(e).__name__)
try:
    pathlib.Path(r'{tamper_ws}').write_text('pwn')
    print('WS_WRITE', 'ALLOWED')
except Exception as e:
    print('WS_WRITE', 'DENIED', type(e).__name__)
try:
    pathlib.Path(r'{outside_write}').write_text('pwn')
    print('OUT_WRITE', 'ALLOWED')
except Exception as e:
    print('OUT_WRITE', 'DENIED', type(e).__name__)
try:
    s = socket.socket()
    s.settimeout(0.5)
    s.connect(('1.1.1.1', 80))
    print('NET', 'ALLOWED')
except Exception as e:
    print('NET', 'DENIED', type(e).__name__)
try:
    val = pathlib.Path(r'{outside_secret}').read_text(encoding='utf-8')
    print('OUT_READ', 'ALLOWED' if 'SUPER_SECRET' in val else 'OTHER')
except Exception as e:
    print('OUT_READ', 'DENIED', type(e).__name__)
"""
    safe_env = {
        k: v
        for k, v in os.environ.items()
        if k in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "VIRTUAL_ENV")
    }
    if sys.platform != "win32":
        safe_env["HOME"] = str(ws)

    res = await execute_in_os_sandbox(
        cmd=[sys.executable, "-B", "-c", probe_code],
        cwd=ws,
        env=safe_env,
        workspace=ws,
        required_read_roots=req_roots,
        optional_read_roots=opt_roots,
        read_only_workspace=True,
        timeout=10.0,
    )
    out = res["stdout"]
    assert "READ_WS OK" in out, f"Unexpected stderr: {res['stderr']}"
    assert "WS_WRITE DENIED" in out and "WS_WRITE ALLOWED" not in out
    assert not tamper_ws.exists()
    assert "OUT_WRITE DENIED" in out and "OUT_WRITE ALLOWED" not in out
    assert not outside_write.exists()
    assert "NET DENIED" in out and "NET ALLOWED" not in out
    if sys.platform != "win32":
        assert "OUT_READ DENIED" in out and "OUT_READ ALLOWED" not in out


# ===========================================================================
# P2-02: Streaming Output Caps Kill Worker Before Unbounded Buffering
# ===========================================================================


@pytest.mark.asyncio
async def test_p2_02_streaming_stdout_flood_kills_worker_before_full_output_buffered(monkeypatch, tmp_path: Path):
    """Streaming reader aborts and SIGKILLs child immediately when stdout exceeds cap (~64KB vs 8MB stream)."""
    ws = (tmp_path / "ws_flood_out").resolve()
    ws.mkdir()
    art = ws / "dummy.txt"
    art.write_text("Legit valid artifact text.", encoding="utf-8")

    # Enforce tight 32 KB limit inside test while child attempts to stream 8 MB slowly over ~10 seconds
    monkeypatch.setattr(worker_mod, "MAX_WORKER_STDOUT_BYTES", 32 * 1024)

    flood_code = (
        "import sys, time\n"
        "chunk = b'X' * 16384\n"
        "for _ in range(512):\n"
        "    sys.stdout.buffer.write(chunk)\n"
        "    sys.stdout.buffer.flush()\n"
        "    time.sleep(0.02)\n"
    )
    spawned_pids: list[int] = []
    if sys.platform == "win32":
        import app.skills.windows_sandbox as win_sb_mod

        orig_win = win_sb_mod.run_windows_appcontainer_sandboxed

        def flood_win(cmd, *args, **kwargs):
            return orig_win([sys.executable, "-c", flood_code], *args, **kwargs)

        monkeypatch.setattr(win_sb_mod, "run_windows_appcontainer_sandboxed", flood_win)
    else:
        orig_exec = asyncio.create_subprocess_exec

        async def flood_exec(*args, **kwargs):
            proc = await orig_exec(
                sys.executable,
                "-c",
                flood_code,
                stdin=kwargs.get("stdin"),
                stdout=kwargs.get("stdout"),
                stderr=kwargs.get("stderr"),
                start_new_session=kwargs.get("start_new_session", True),
            )
            spawned_pids.append(proc.pid)
            return proc

        monkeypatch.setattr(asyncio, "create_subprocess_exec", flood_exec)

    started = time.monotonic()
    ok, detail = await verify_artifact_in_worker(art, workspace=ws, timeout=8.0)
    elapsed = time.monotonic() - started

    assert ok is False
    assert "melebihi batas" in detail.lower()
    assert "stdout" in detail.lower()
    # Must terminate almost immediately (~0.1s), well before the 8s timeout / 10s flood duration
    assert elapsed < 3.0, f"Worker took too long ({elapsed:.2f}s) instead of killing on streaming threshold"
    if sys.platform != "win32":
        assert len(spawned_pids) == 1
        with pytest.raises(ProcessLookupError):
            os.kill(spawned_pids[0], 0)


@pytest.mark.asyncio
async def test_p2_02_streaming_stderr_flood_kills_worker_and_caps_diagnostic_snippet(monkeypatch, tmp_path: Path):
    """Streaming stderr cap kills runaway noise immediately and truncates normal stderr to snippet limit."""
    ws = (tmp_path / "ws_flood_err").resolve()
    ws.mkdir()
    art = ws / "dummy.txt"
    art.write_text("Legit valid artifact text.", encoding="utf-8")

    monkeypatch.setattr(worker_mod, "MAX_WORKER_STDERR_BYTES", 16 * 1024)
    monkeypatch.setattr(worker_mod, "MAX_WORKER_STDERR_SNIPPET_BYTES", 256)

    err_flood_code = (
        "import sys, time\n"
        "chunk = b'E' * 8192\n"
        "for _ in range(512):\n"
        "    sys.stderr.buffer.write(chunk)\n"
        "    sys.stderr.buffer.flush()\n"
        "    time.sleep(0.02)\n"
    )
    if sys.platform == "win32":
        import app.skills.windows_sandbox as win_sb_mod

        orig_win = win_sb_mod.run_windows_appcontainer_sandboxed

        def err_win(cmd, *args, **kwargs):
            return orig_win([sys.executable, "-c", err_flood_code], *args, **kwargs)

        monkeypatch.setattr(win_sb_mod, "run_windows_appcontainer_sandboxed", err_win)
    else:
        orig_exec = asyncio.create_subprocess_exec

        async def err_exec(*args, **kwargs):
            return await orig_exec(
                sys.executable,
                "-c",
                err_flood_code,
                stdin=kwargs.get("stdin"),
                stdout=kwargs.get("stdout"),
                stderr=kwargs.get("stderr"),
                start_new_session=kwargs.get("start_new_session", True),
            )

        monkeypatch.setattr(asyncio, "create_subprocess_exec", err_exec)

    started = time.monotonic()
    ok, detail = await verify_artifact_in_worker(art, workspace=ws, timeout=8.0)
    elapsed = time.monotonic() - started

    assert ok is False
    assert "stderr" in detail.lower() and "melebihi batas" in detail.lower()
    assert elapsed < 3.0

    # Undo subprocess monkeypatch before exercising real sandbox stderr diagnostic capping
    monkeypatch.undo()

    # Verify execute_in_os_sandbox retains ONLY <= stderr_retain_bytes when non-zero exit stays below hard cap
    req_roots, opt_roots = collect_python_runtime_read_roots()
    if has_real_os_sandbox:
        sb_env = {
            k: v
            for k, v in os.environ.items()
            if k in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "VIRTUAL_ENV", "TEMP", "TMP")
        }
        if sys.platform != "win32":
            sb_env["HOME"] = str(ws)

        noisy_res = await execute_in_os_sandbox(
            cmd=[sys.executable, "-B", "-c", "import sys; sys.stderr.write('Z' * 4000); sys.exit(2)"],
            cwd=ws,
            env=sb_env,
            workspace=ws,
            required_read_roots=req_roots,
            optional_read_roots=opt_roots,
            read_only_workspace=True,
            max_output_bytes=64 * 1024,
            max_stderr_bytes=16 * 1024,
            stderr_retain_bytes=256,
            abort_on_output_limit=True,
        )
        assert noisy_res["exit_code"] == 2
        assert len(noisy_res["stderr"]) == 256

        # Verify REAL unsuppressed OS sandbox kills streaming flood in < 3s without full buffering
        flood_start = time.monotonic()
        with pytest.raises(SandboxOutputLimitError) as limit_exc:
            await execute_in_os_sandbox(
                cmd=[sys.executable, "-B", "-c", "import sys, time\nfor _ in range(512): sys.stdout.buffer.write(b'Q' * 16384); sys.stdout.buffer.flush(); time.sleep(0.02)"],
                cwd=ws,
                env=sb_env,
                workspace=ws,
                required_read_roots=req_roots,
                optional_read_roots=opt_roots,
                read_only_workspace=True,
                timeout=8.0,
                max_output_bytes=32 * 1024,
                max_stderr_bytes=16 * 1024,
                stderr_retain_bytes=256,
                abort_on_output_limit=True,
            )
        assert limit_exc.value.stream == "stdout"
        assert (time.monotonic() - flood_start) < 3.0


# ===========================================================================
# Hardening: TOCTOU / Intermediate Symlink Escape & Minimal Module Surface
# ===========================================================================


@pytest.mark.asyncio
async def test_p2_01_verifier_rejects_intermediate_symlink_escape_before_and_during_open(tmp_path: Path):
    """Intermediate symlinks inside workspace pointing outside are rejected fail-closed."""
    outside = tmp_path / "outside_dir"
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("TOP SECRET OUTSIDE WORKSPACE", encoding="utf-8")

    ws = tmp_path / "ws_sym"
    ws.mkdir()
    sub_link = ws / "subdir_link"
    try:
        sub_link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation requires elevated privileges on this Windows host")

    target = sub_link / "secret.txt"
    bd = get_artifact_postcondition_breakdown(target, workspace=ws)
    assert bd["file_created"] is False
    assert "symlink" in bd["detail"].lower() or "luar" in bd["detail"].lower()

    ok_w, msg_w = await verify_artifact_in_worker(target, workspace=ws)
    assert ok_w is False
    assert "symlink" in msg_w.lower() or "luar" in msg_w.lower()


def test_verifier_module_has_zero_heavy_app_config_or_network_imports():
    """app/core/artifact_verifier.py must stay isolated from FastAPI, DB, LLM, and EngineConfig."""
    verifier_src = (ENGINE_ROOT / "app" / "core" / "artifact_verifier.py").read_text(encoding="utf-8")
    tree = ast.parse(verifier_src)
    forbidden_prefixes = ("app.config", "app.api", "app.db", "app.tools", "litellm", "fastapi", "aiosqlite")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden_prefixes), f"Forbidden import {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert not mod.startswith(forbidden_prefixes), f"Forbidden from-import {mod}"


def test_hardening_malformed_ooxml_zip_traversal_and_corrupt_pdf_fail_closed(tmp_path: Path):
    """Adversarial malformed ZIP/OOXML traversal entries, bogus OOXML, and corrupt PDFs fail closed."""
    import zipfile

    # 1. ZIP entry path traversal inside .xlsx
    trav_xlsx = tmp_path / "trav.xlsx"
    with zipfile.ZipFile(trav_xlsx, "w") as zf:
        zf.writestr("../../outside.xml", "<x/>")
    bd_trav = get_artifact_postcondition_breakdown(trav_xlsx, workspace=tmp_path)
    assert bd_trav["semantic_postcondition_passed"] is False
    assert "berbahaya" in bd_trav["detail"].lower() or "traversal" in bd_trav["detail"].lower()

    # 2. Fake .docx (random garbage bytes)
    bad_docx = tmp_path / "garbage.docx"
    bad_docx.write_bytes(b"NOT_A_ZIP_HEADER_000000")
    bd_docx = get_artifact_postcondition_breakdown(bad_docx, workspace=tmp_path)
    assert bd_docx["format_valid"] is False
    assert bd_docx["semantic_postcondition_passed"] is False

    # 3. Truncated / corrupt PDF
    bad_pdf = tmp_path / "corrupt.pdf"
    bad_pdf.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Truncated")
    bd_pdf = get_artifact_postcondition_breakdown(bad_pdf, workspace=tmp_path)
    assert bd_pdf["format_valid"] is False
    assert bd_pdf["semantic_postcondition_passed"] is False

