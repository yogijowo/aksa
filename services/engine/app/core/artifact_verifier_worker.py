"""OS-Sandboxed & Streaming-Bounded Artifact Verifier Worker (Cycle 9–11 Hardened).

Executes document parsing and postcondition validation inside a kernel-enforced OS sandbox
(macOS Seatbelt ``(deny default)``, Linux Bubblewrap namespaces with ``--ro-bind`` + ``--remount-ro /``,
and Windows zero-capability AppContainer + Job Object):
- Read-only workspace mount/ACL (zero filesystem write capability outside ``/dev/null``).
- Network completely denied at kernel level.
- OS resource caps compatible with multi-threaded native parser dependencies such as OpenBLAS/numpy
  (positive bounded ``RLIMIT_NPROC`` rather than ``0``, single-threaded BLAS env, ``RLIMIT_FSIZE=0``,
  ``RLIMIT_CPU``, ``RLIMIT_NOFILE``, ``RLIMIT_AS``/``RLIMIT_DATA``, or Windows Job Object limits).
- Streaming chunked readers with hard caps on BOTH ``stdout`` and ``stderr`` that kill the
  process group / Job Object immediately upon limit breach before unbounded buffering occurs.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

MAX_WORKER_STDIN_BYTES = 512 * 1024
MAX_WORKER_STDOUT_BYTES = 512 * 1024
MAX_WORKER_STDERR_BYTES = 64 * 1024
MAX_WORKER_STDERR_SNIPPET_BYTES = 2048
WORKER_MEMORY_LIMIT_BYTES = 768 * 1024 * 1024
DEFAULT_WORKER_MAX_NPROC_HEADROOM = 32


def _estimate_current_uid_tasks() -> int | None:
    """Count active tasks/threads owned by current UID on Linux for positive bounded RLIMIT_NPROC."""
    if not sys.platform.startswith("linux"):
        return None
    my_uid = os.getuid()
    total_threads = 0
    try:
        for entry in os.scandir("/proc"):
            if not entry.name.isdigit():
                continue
            try:
                with open(f"/proc/{entry.name}/status", "r", encoding="utf-8", errors="ignore") as fp:
                    uid_line = ""
                    thr_line = ""
                    for line in fp:
                        if line.startswith("Uid:"):
                            uid_line = line
                        elif line.startswith("Threads:"):
                            thr_line = line
                        if uid_line and thr_line:
                            break
                    if uid_line:
                        real_uid = int(uid_line.split()[1])
                        if real_uid == my_uid:
                            total_threads += int(thr_line.split()[1]) if thr_line else 1
            except OSError:
                continue
    except OSError:
        return None
    return total_threads if total_threads > 0 else None


def _apply_worker_resource_limits(timeout_sec: float = 10.0) -> None:
    """Apply defense-in-depth POSIX OS resource limits without breaking native thread pools."""
    if sys.platform == "win32":
        return
    try:
        import resource
    except Exception:
        return

    def _clamp_set(rsrc_name: str, target: int) -> bool:
        rsrc = getattr(resource, rsrc_name, None)
        if rsrc is None:
            return False
        try:
            cur_soft, cur_hard = resource.getrlimit(rsrc)
            eff = target if cur_hard == resource.RLIM_INFINITY else min(target, cur_hard)
            eff_soft = eff if cur_soft == resource.RLIM_INFINITY else min(eff, cur_soft)
            resource.setrlimit(rsrc, (eff_soft, eff))
            return True
        except Exception:
            return False

    # Cycle 11 P1-01: NEVER set RLIMIT_NPROC=0 on Linux (causes OpenBLAS pthread_create EAGAIN).
    # Enforce a strictly positive bounded process/thread ceiling when known, >= 64 otherwise.
    raw_nproc = os.environ.get("AKSA_VERIFIER_MAX_NPROC", "").strip()
    try:
        nproc_limit = max(32, int(raw_nproc)) if raw_nproc else 64
    except ValueError:
        nproc_limit = 64
    _clamp_set("RLIMIT_NPROC", nproc_limit)

    _clamp_set("RLIMIT_FSIZE", 0)
    _clamp_set("RLIMIT_CPU", max(5, int(timeout_sec) + 2))
    _clamp_set("RLIMIT_NOFILE", 256)
    if not _clamp_set("RLIMIT_AS", WORKER_MEMORY_LIMIT_BYTES):
        _clamp_set("RLIMIT_DATA", WORKER_MEMORY_LIMIT_BYTES)


def _install_worker_process_guards() -> None:
    """Block Python child-process creation primitives while allowing native library pthreads."""
    def _blocked_proc(*args: Any, **kwargs: Any) -> Any:
        raise PermissionError("Pembuatan sub-proses diblokir di worker verifikasi AKSA.")

    for fn_name in (
        "system",
        "popen",
        "fork",
        "forkpty",
        "posix_spawn",
        "posix_spawnp",
        "spawnl",
        "spawnlp",
        "spawnv",
        "spawnvp",
        "execl",
        "execv",
    ):
        if hasattr(os, fn_name):
            try:
                setattr(os, fn_name, _blocked_proc)
            except Exception:
                pass
    try:
        import subprocess
        subprocess.Popen = _blocked_proc  # type: ignore[assignment]
        subprocess.run = _blocked_proc  # type: ignore[assignment]
        subprocess.call = _blocked_proc  # type: ignore[assignment]
    except Exception:
        pass
    sys.modules["_posixsubprocess"] = None  # type: ignore[assignment]


def _verify_sync_in_subprocess(payload: dict[str, Any]) -> dict[str, Any]:
    from app.core.artifact_verifier import (
        MAX_ARTIFACT_VERIFY_BYTES,
        check_no_symlink_components,
        get_artifact_postcondition_breakdown,
        sanitize_verifier_schema,
    )

    art_raw = str(payload.get("artifact_path", "") or "").strip()
    ws_raw = str(payload.get("workspace", "") or "").strip()
    if not art_raw:
        return {"ok": False, "detail": "Path artefak worker kosong.", "breakdown": {}}

    art_path = Path(art_raw)
    ws_path: Path | None = Path(ws_raw) if ws_raw else None
    sym_ok, sym_err = check_no_symlink_components(art_path, workspace=ws_path)
    if not sym_ok:
        return {"ok": False, "detail": sym_err, "breakdown": {}}

    schema = sanitize_verifier_schema(payload.get("expected_schema"))
    if "expected_schema" not in payload:
        schema["max_bytes"] = MAX_ARTIFACT_VERIFY_BYTES

    breakdown = get_artifact_postcondition_breakdown(
        art_path,
        expected_schema=schema,
        workspace=ws_path,
    )
    ok = bool(
        breakdown.get("file_created")
        and breakdown.get("format_valid")
        and breakdown.get("content_detected")
        and breakdown.get("task_requirement_satisfied")
        and breakdown.get("semantic_postcondition_passed")
        and not breakdown.get("unsupported_format")
    )
    return {"ok": ok, "detail": str(breakdown.get("detail", "")), "breakdown": breakdown}


async def verify_artifact_in_worker(
    art_path: Path,
    *,
    expected_schema: dict[str, Any] | None = None,
    workspace: Path | None = None,
    timeout: float = 10.0,
) -> tuple[bool, str]:
    """Run ``get_artifact_postcondition_breakdown`` inside a read-only, no-net OS sandbox worker."""
    from app.core.artifact_verifier import check_no_symlink_components
    from app.skills.os_sandbox import (
        SandboxOutputLimitError,
        SandboxUnavailableError,
        collect_python_runtime_read_roots,
        execute_in_os_sandbox,
    )
    from app.skills.windows_sandbox import validate_sandbox_read_root

    if not str(art_path or "").strip():
        return False, "Path artefak verifikasi kosong."

    if workspace is not None:
        if workspace.is_symlink():
            return False, "Workspace verifikasi berupa symlink ditolak (fail-closed)."
        if not workspace.exists() or not workspace.is_dir():
            return False, f"Workspace verifikasi tidak valid: {workspace}"
        ws_real = workspace.resolve()
    else:
        if art_path.is_symlink():
            return False, f"Artefak symlink ditolak oleh gerbang verifikasi: {art_path}"
        ws_real = art_path.resolve(strict=False).parent
        if not ws_real.exists() or not ws_real.is_dir():
            return False, f"File tidak ditemukan: {art_path}"

    try:
        ws_real = validate_sandbox_read_root(ws_real, allow_system_usr=False)
    except PermissionError as exc:
        return False, f"Sandbox OS verifikasi menolak workspace terlalu luas (fail-closed): {exc}"

    sym_ok, sym_err = check_no_symlink_components(art_path, workspace=ws_real)
    if not sym_ok:
        return False, sym_err

    canonical_art = art_path.resolve(strict=False)
    request_bytes = json.dumps(
        {
            "artifact_path": str(canonical_art),
            "workspace": str(ws_real),
            "expected_schema": expected_schema or {},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    if len(request_bytes) > MAX_WORKER_STDIN_BYTES:
        return False, "Payload verifikasi artefak melebihi batas stdin aman."

    engine_root = str(Path(__file__).resolve().parent.parent.parent)
    allow_env_keys = (
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "VIRTUAL_ENV",
        "TMPDIR",
        "TEMP",
        "TMP",
    )
    safe_env = {k: v for k, v in os.environ.items() if k in allow_env_keys}
    safe_env["PYTHONPATH"] = engine_root
    safe_env["PYTHONDONTWRITEBYTECODE"] = "1"
    safe_env["PYTHONNOUSERSITE"] = "1"
    safe_env["AKSA_VERIFIER_TIMEOUT"] = str(float(timeout))
    # Cap native library thread pools (OpenBLAS/OMP) cleanly before dynamic libraries initialize
    safe_env["OPENBLAS_NUM_THREADS"] = "1"
    safe_env["OMP_NUM_THREADS"] = "1"
    safe_env["MKL_NUM_THREADS"] = "1"
    safe_env["BLIS_NUM_THREADS"] = "1"
    safe_env["VECLIB_MAXIMUM_THREADS"] = "1"
    safe_env["NUMEXPR_NUM_THREADS"] = "1"
    safe_env["MALLOC_ARENA_MAX"] = "2"
    if sys.platform != "win32":
        safe_env["HOME"] = str(ws_real)
        safe_env["TMPDIR"] = str(ws_real)
        uid_tasks = _estimate_current_uid_tasks()
        if uid_tasks is not None:
            safe_env["AKSA_VERIFIER_MAX_NPROC"] = str(max(64, uid_tasks + DEFAULT_WORKER_MAX_NPROC_HEADROOM))

    req_roots, opt_roots = collect_python_runtime_read_roots()

    try:
        res = await execute_in_os_sandbox(
            cmd=[sys.executable, "-B", "-m", "app.core.artifact_verifier_worker"],
            cwd=ws_real,
            env=safe_env,
            workspace=ws_real,
            required_read_roots=req_roots,
            optional_read_roots=opt_roots,
            stdin_bytes=request_bytes,
            read_only_workspace=True,
            timeout=timeout,
            max_output_bytes=MAX_WORKER_STDOUT_BYTES,
            max_stderr_bytes=MAX_WORKER_STDERR_BYTES,
            stderr_retain_bytes=MAX_WORKER_STDERR_SNIPPET_BYTES,
            abort_on_output_limit=True,
        )
    except TimeoutError:
        return False, f"Verifikasi artefak '{art_path.name}' dihentikan paksa (timeout {timeout}s)."
    except SandboxOutputLimitError as exc:
        return (
            False,
            f"Output {exc.stream} worker verifikasi melebihi batas ukuran aman ({exc.limit} bytes); proses dihentikan.",
        )
    except SandboxUnavailableError as exc:
        return False, f"Sandbox OS verifikasi tidak tersedia (fail-closed): {exc}"

    exit_code = int(res.get("exit_code", 1))
    stdout_str = str(res.get("stdout", "") or "")
    stderr_str = str(res.get("stderr", "") or "")

    if exit_code != 0:
        err_snip = stderr_str[:MAX_WORKER_STDERR_SNIPPET_BYTES].strip()
        return False, f"Worker verifikasi artefak gagal (exit={exit_code}): {err_snip}"

    try:
        parsed = json.loads(stdout_str)
        return bool(parsed.get("ok")), str(parsed.get("detail", ""))
    except Exception as exc:
        return False, f"Respons worker verifikasi tidak valid: {exc}"


if __name__ == "__main__":
    import mimetypes

    # Avoid probing /etc/apache2/mime.types inside strict Seatbelt/bwrap sandboxes
    mimetypes.knownfiles = []
    mimetypes.init()

    cpu_hint = 10.0
    try:
        cpu_hint = float(os.environ.get("AKSA_VERIFIER_TIMEOUT", "10.0"))
    except (TypeError, ValueError):
        pass
    _apply_worker_resource_limits(timeout_sec=cpu_hint)
    _install_worker_process_guards()

    raw = sys.stdin.buffer.read(MAX_WORKER_STDIN_BYTES + 1)
    if len(raw) > MAX_WORKER_STDIN_BYTES:
        sys.stdout.write(json.dumps({"ok": False, "detail": "Payload worker melebihi batas.", "breakdown": {}}))
        sys.exit(0)
    try:
        req = json.loads(raw.decode("utf-8"))
        out = _verify_sync_in_subprocess(req if isinstance(req, dict) else {})
    except Exception as exc:
        out = {"ok": False, "detail": f"Kesalahan internal worker verifikasi: {exc}", "breakdown": {}}
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    sys.stdout.flush()
