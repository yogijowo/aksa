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
import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAX_WORKER_STDIN_BYTES = 512 * 1024
MAX_WORKER_STDOUT_BYTES = 512 * 1024
MAX_WORKER_STDERR_BYTES = 64 * 1024
MAX_WORKER_STDERR_SNIPPET_BYTES = 2048
WORKER_MEMORY_LIMIT_BYTES = 768 * 1024 * 1024
DEFAULT_WORKER_FALLBACK_UID_TASKS = 64
MIN_WORKER_MAX_NPROC = 64
MAX_WORKER_NPROC_CEILING = 4096
DEFAULT_WORKER_MAX_NPROC_HEADROOM = 64
MIN_WORKER_MAX_NPROC_HEADROOM = 16
MAX_WORKER_MAX_NPROC_HEADROOM = 512


def _resolve_system_nproc_hard_limit() -> int | None:
    """Inspect OS hard ceiling for RLIMIT_NPROC when bounded on POSIX systems."""
    if sys.platform == "win32":
        return None
    try:
        import resource

        rsrc = getattr(resource, "RLIMIT_NPROC", None)
        if rsrc is None:
            return None
        _soft, hard = resource.getrlimit(rsrc)
        if hard != resource.RLIM_INFINITY and int(hard) > 0:
            return int(hard)
    except Exception:
        pass
    return None


def _clamp_worker_nproc_to_ceiling(target_limit: int, hard_limit: int | None) -> int:
    """Keep worker NPROC limit strictly positive and within system hard limit."""
    effective_ceiling = (
        min(MAX_WORKER_NPROC_CEILING, int(hard_limit))
        if (hard_limit is not None and int(hard_limit) > 0)
        else MAX_WORKER_NPROC_CEILING
    )
    if effective_ceiling < MIN_WORKER_MAX_NPROC:
        return max(1, min(int(target_limit), effective_ceiling))
    return min(effective_ceiling, max(MIN_WORKER_MAX_NPROC, int(target_limit)))


def _resolve_worker_nproc_headroom(uid_tasks: int | None = None) -> int:
    """Resolve configurable or load-adaptive positive headroom above current UID tasks."""
    raw = os.environ.get("AKSA_VERIFIER_NPROC_HEADROOM", "").strip()
    if raw:
        try:
            val = int(raw)
            return min(MAX_WORKER_MAX_NPROC_HEADROOM, max(MIN_WORKER_MAX_NPROC_HEADROOM, val))
        except ValueError:
            pass
    if uid_tasks is not None and uid_tasks > 0:
        adaptive = max(DEFAULT_WORKER_MAX_NPROC_HEADROOM, int(uid_tasks * 0.5))
        return min(MAX_WORKER_MAX_NPROC_HEADROOM, adaptive)
    return DEFAULT_WORKER_MAX_NPROC_HEADROOM


def _compute_initial_worker_nproc_limit(
    uid_tasks: int | None,
    headroom: int,
    *,
    hard_limit: int | None = None,
) -> tuple[int, str]:
    """Compute initial positive RLIMIT_NPROC budget with deterministic fallback when UID count is None."""
    if uid_tasks is not None and int(uid_tasks) > 0:
        baseline = int(uid_tasks)
        source = "proc_uid_tasks"
    else:
        baseline = DEFAULT_WORKER_FALLBACK_UID_TASKS
        source = "deterministic_fallback"
    raw_target = max(MIN_WORKER_MAX_NPROC, baseline + max(MIN_WORKER_MAX_NPROC_HEADROOM, int(headroom)))
    return _clamp_worker_nproc_to_ceiling(raw_target, hard_limit), source


def _compute_retry_worker_nproc_limit(
    previous_limit: int,
    uid_tasks: int | None,
    headroom: int,
    *,
    hard_limit: int | None = None,
) -> tuple[int, str]:
    """Compute strictly escalated RLIMIT_NPROC limit anchored on previous attempt & hard ceiling."""
    prev = max(MIN_WORKER_MAX_NPROC, int(previous_limit))
    step_up = max(MIN_WORKER_MAX_NPROC, int(headroom))
    escalated_from_prev = max(prev + step_up, prev * 2)
    if uid_tasks is not None and int(uid_tasks) > 0:
        from_uid = int(uid_tasks) + max(MIN_WORKER_MAX_NPROC_HEADROOM, int(headroom))
        raw_next = max(escalated_from_prev, from_uid)
        source = "proc_uid_tasks_retry"
    else:
        raw_next = escalated_from_prev
        source = "deterministic_fallback_retry"
    return _clamp_worker_nproc_to_ceiling(raw_next, hard_limit), source


def _is_rlimit_nproc_eagain(stderr_text: str) -> bool:
    """Detect POSIX pthread_create / RLIMIT_NPROC resource exhaustion errors for telemetry & retry."""
    low = (stderr_text or "").lower()
    return any(
        tok in low
        for tok in (
            "resource temporarily unavailable",
            "pthread_create failed",
            "rlimit_nproc",
            "eagain",
        )
    )


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

    def _clamp_set(rsrc_name: str, target: int, *, allow_raise_soft_to_hard: bool = False) -> bool:
        rsrc = getattr(resource, rsrc_name, None)
        if rsrc is None:
            return False
        try:
            cur_soft, cur_hard = resource.getrlimit(rsrc)
            eff = target if cur_hard == resource.RLIM_INFINITY else min(target, cur_hard)
            if allow_raise_soft_to_hard:
                eff_soft = eff
            else:
                eff_soft = eff if cur_soft == resource.RLIM_INFINITY else min(eff, cur_soft)
            resource.setrlimit(rsrc, (eff_soft, eff))
            return True
        except Exception:
            return False

    # Cycle 11–13: NEVER set RLIMIT_NPROC=0 on POSIX (causes OpenBLAS pthread_create EAGAIN).
    # Enforce a strictly positive bounded process/thread ceiling with deterministic fallback.
    raw_nproc = os.environ.get("AKSA_VERIFIER_MAX_NPROC", "").strip()
    try:
        parsed_nproc = int(raw_nproc) if raw_nproc else MIN_WORKER_MAX_NPROC
    except ValueError:
        parsed_nproc = MIN_WORKER_MAX_NPROC
    nproc_limit = _clamp_worker_nproc_to_ceiling(max(MIN_WORKER_MAX_NPROC, parsed_nproc), None)
    _clamp_set("RLIMIT_NPROC", nproc_limit, allow_raise_soft_to_hard=True)

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

    req_roots, opt_roots = collect_python_runtime_read_roots()
    worker_cmd = (
        [sys.executable, "--verifier-worker"]
        if getattr(sys, "frozen", False)
        else [sys.executable, "-B", "-m", "app.core.artifact_verifier_worker"]
    )

    is_posix = sys.platform != "win32"
    uid_tasks = _estimate_current_uid_tasks() if is_posix else None
    headroom = _resolve_worker_nproc_headroom(uid_tasks)
    hard_limit = _resolve_system_nproc_hard_limit() if is_posix else None
    current_nproc_limit, nproc_source = (
        _compute_initial_worker_nproc_limit(uid_tasks, headroom, hard_limit=hard_limit)
        if is_posix
        else (0, "windows_job_object")
    )
    max_attempts = 2 if is_posix else 1

    res: dict[str, Any] = {}
    for attempt in range(max_attempts):
        attempt_env = dict(safe_env)
        if is_posix:
            attempt_env["AKSA_VERIFIER_MAX_NPROC"] = str(current_nproc_limit)

        try:
            res = await execute_in_os_sandbox(
                cmd=worker_cmd,
                cwd=ws_real,
                env=attempt_env,
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

        if exit_code != 0 and _is_rlimit_nproc_eagain(stderr_str):
            logger.warning(
                "verifier_worker.rlimit_nproc_eagain attempt=%d max_attempts=%d source=%s current_nproc=%d headroom=%d uid_tasks=%s hard_limit=%s exit_code=%d",
                attempt + 1,
                max_attempts,
                nproc_source,
                current_nproc_limit,
                headroom,
                uid_tasks,
                hard_limit,
                exit_code,
            )
            if is_posix and attempt + 1 < max_attempts:
                next_headroom = min(MAX_WORKER_MAX_NPROC_HEADROOM, max(headroom * 2, headroom + 64))
                new_uid_tasks = _estimate_current_uid_tasks() if sys.platform.startswith("linux") else None
                next_limit, next_source = _compute_retry_worker_nproc_limit(
                    current_nproc_limit,
                    new_uid_tasks,
                    next_headroom,
                    hard_limit=hard_limit,
                )
                if next_limit <= current_nproc_limit:
                    logger.error(
                        "verifier_worker.rlimit_nproc_retry_blocked attempt=%d source=%s current_nproc=%d hard_limit=%s",
                        attempt + 1,
                        nproc_source,
                        current_nproc_limit,
                        hard_limit,
                    )
                    return (
                        False,
                        f"Worker verifikasi artefak gagal akibat batas proses/thread OS "
                        f"(RLIMIT_NPROC={current_nproc_limit}, hard_limit={hard_limit or MAX_WORKER_NPROC_CEILING}); "
                        "retry dihentikan secara terkontrol karena batas maksimum telah tercapai.",
                    )
                logger.warning(
                    "verifier_worker.rlimit_nproc_retrying next_attempt=%d prev_nproc=%d next_nproc=%d prev_headroom=%d next_headroom=%d source=%s",
                    attempt + 2,
                    current_nproc_limit,
                    next_limit,
                    headroom,
                    next_headroom,
                    next_source,
                )
                headroom = next_headroom
                current_nproc_limit = next_limit
                nproc_source = next_source
                if new_uid_tasks is not None:
                    uid_tasks = new_uid_tasks
                continue
            logger.error(
                "verifier_worker.rlimit_nproc_exhausted attempts=%d final_nproc=%d hard_limit=%s source=%s exit_code=%d",
                attempt + 1,
                current_nproc_limit,
                hard_limit,
                nproc_source,
                exit_code,
            )
        break

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


def run_verifier_worker_stdio() -> int:
    """Stdio entrypoint executed inside the OS-sandboxed verifier child process."""
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
        return 0
    try:
        req = json.loads(raw.decode("utf-8"))
        out = _verify_sync_in_subprocess(req if isinstance(req, dict) else {})
    except Exception as exc:
        out = {"ok": False, "detail": f"Kesalahan internal worker verifikasi: {exc}", "breakdown": {}}
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(run_verifier_worker_stdio())
