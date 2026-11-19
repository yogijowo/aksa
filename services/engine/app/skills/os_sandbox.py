"""OS-enforced sandbox wrapper and dispatcher for third-party skill scripts (AKSA-SEC-003-R5).

The in-process hooks in ``sandbox_runner`` are defense-in-depth only. The security
boundary is strictly enforced by the host operating system:

* macOS : ``sandbox-exec`` (Seatbelt) least-privilege ``(deny default)`` profile.
* Linux : ``bwrap`` (bubblewrap) unshared namespaces with scoped read-only system mounts.
* Windows : Zero-capability AppContainer + Suspended Job Object launcher
            (``app.skills.windows_sandbox``).
* Other : No OS sandbox -> execution is REFUSED (fail-closed ``SandboxUnavailableError``).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import signal
import sys
from pathlib import Path
from typing import Any


class SandboxUnavailableError(PermissionError):
    """Raised when no OS-enforced sandbox exists or setup fails (fail-closed)."""


def _seatbelt_quote(path: str) -> str:
    return '"' + path.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _collect_macos_python_runtime_roots(read_roots: list[Path]) -> tuple[list[Path], list[Path]]:
    """Return (executable_literals, runtime_read_subpaths) for minimal macOS Seatbelt access."""
    exec_literals: list[Path] = []
    seen_exec: set[str] = set()

    def _add_exec(p: Path) -> None:
        s = str(p)
        if s not in seen_exec:
            seen_exec.add(s)
            exec_literals.append(p)

    py_raw = Path(sys.executable)
    _add_exec(py_raw)
    try:
        py_resolved = py_raw.resolve()
        _add_exec(py_resolved)
        # macOS Framework Python delegates execution to Resources/Python.app/Contents/MacOS/Python
        fw_app = py_resolved.parent.parent / "Resources" / "Python.app" / "Contents" / "MacOS" / "Python"
        if fw_app.exists():
            _add_exec(fw_app)
    except Exception:
        pass

    subpaths: list[Path] = []
    seen_sub: set[str] = set()

    def _add_sub(p: Path) -> None:
        try:
            rp = p.resolve()
            s = str(rp)
            if s not in seen_sub:
                seen_sub.add(s)
                subpaths.append(rp)
        except Exception:
            pass

    for r in read_roots:
        _add_sub(r)
        # Include resolved Python.framework / Cellar / opt root if applicable
        try:
            rp = r.resolve()
            for parent in [rp, *rp.parents]:
                if parent.name == "Python.framework" or (
                    parent.parent.name == "Cellar" and parent.name.startswith("python")
                ):
                    _add_sub(parent)
                    break
        except Exception:
            pass

    # Standard Homebrew/Framework shared libs dynamically linked by Python stdlib C-extensions
    for opt_lib in (
        Path("/opt/homebrew/opt"),
        Path("/opt/homebrew/Cellar/openssl@3"),
        Path("/opt/homebrew/Cellar/sqlite"),
        Path("/opt/homebrew/Cellar/xz"),
        Path("/opt/homebrew/Cellar/mpdecimal"),
        Path("/usr/local/opt"),
    ):
        if opt_lib.exists():
            _add_sub(opt_lib)

    return exec_literals, subpaths


def build_seatbelt_profile(workspace: Path, read_roots: list[Path]) -> str:
    """Build a strict macOS Seatbelt least-privilege ``(deny default)`` profile."""
    from app.skills.windows_sandbox import validate_sandbox_read_root

    ws_resolved = validate_sandbox_read_root(workspace)
    validated_roots = [validate_sandbox_read_root(r) for r in read_roots]
    ws = _seatbelt_quote(str(ws_resolved))
    exec_literals, runtime_subpaths = _collect_macos_python_runtime_roots([ws_resolved, *validated_roots])

    exec_rules = "\n".join(f"    (literal {_seatbelt_quote(str(e))})" for e in exec_literals)
    read_rules = "\n".join(f"    (subpath {_seatbelt_quote(str(p))})" for p in runtime_subpaths)

    map_exec_dirs = [
        Path("/System"),
        Path("/usr/lib"),
        Path("/Library/Frameworks"),
        *runtime_subpaths,
    ]
    seen_map: set[str] = set()
    map_rules_list: list[str] = []
    for d in map_exec_dirs:
        s = str(d)
        if s not in seen_map:
            seen_map.add(s)
            map_rules_list.append(f"    (subpath {_seatbelt_quote(s)})")
    map_rules = "\n".join(map_rules_list)

    return f"""(version 1)
(deny default)
(deny network*)
(deny process-fork)
(allow signal (target self))
(allow sysctl-read)
(allow file-read-metadata)
(allow process-exec
{exec_rules}
)
(allow file-map-executable
{map_rules}
)
(allow file-read-data
    (literal "/")
    (literal "/private")
    (literal "/private/var")
    (literal "/dev")
    (literal "/dev/null")
    (literal "/dev/urandom")
    (literal "/dev/random")
    (literal "/dev/zero")
    (subpath "/System/Library")
    (subpath "/System/Cryptexes")
    (subpath "/System/Volumes/Preboot/Cryptexes")
    (subpath "/usr/lib")
    (subpath "/usr/share")
    (subpath "/Library/Apple")
    (subpath "/private/var/db/timezone")
{read_rules}
)
(allow file-write*
    (subpath {ws})
    (literal "/dev/null")
)
"""


def build_linux_bwrap_args(workspace: Path, read_roots: list[Path], cmd: list[str]) -> list[str]:
    """Build hardened bubblewrap namespace arguments avoiding full host root or /usr/local exposure."""
    from app.skills.windows_sandbox import validate_sandbox_read_root

    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise SandboxUnavailableError(
            "bubblewrap (bwrap) tidak ditemukan; eksekusi skrip ditolak (fail-closed)."
        )
    ws = str(validate_sandbox_read_root(workspace, allow_system_usr=False))
    args: list[str] = [
        bwrap,
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--cap-drop", "ALL",
        "--hostname", "aksa-sandbox",
        "--dev", "/dev",
        "--proc", "/proc",
    ]
    # Expose only minimal scoped system runtime subpaths read-only
    # (never expose /, /usr/local, /home, /root, /run, /var, /sys, or /etc secrets)
    for sys_ro in (
        "/usr/bin",
        "/usr/lib",
        "/usr/lib64",
        "/usr/libexec",
        "/usr/share",
        "/lib",
        "/lib64",
        "/bin",
        "/etc/alternatives",
        "/etc/ld.so.cache",
        "/etc/ssl/certs",
    ):
        if Path(sys_ro).exists():
            args.extend(["--ro-bind-try", sys_ro, sys_ro])
    for r in read_roots:
        resolved_path = validate_sandbox_read_root(r, allow_system_usr=True)
        resolved = str(resolved_path)
        if resolved in {ws, "/usr"}:
            # Skip /usr itself so /usr/local is never implicitly exposed when sys.base_prefix == '/usr'
            continue
        args.extend(["--ro-bind-try", resolved, resolved])
    # Mount writable workspace BEFORE locking container root `/` read-only (`--remount-ro /`)
    # so parent directories such as `/tmp` or synthetic `/home` stubs cannot accept outside writes.
    args.extend([
        "--bind", ws, ws,
        "--remount-ro", "/",
        "--chdir", ws,
        "--setenv", "TMPDIR", ws,
        *cmd,
    ])
    return args


def wrap_command(cmd: list[str], workspace: Path, read_roots: list[Path]) -> list[str]:
    """Return ``cmd`` wrapped in a CLI OS sandbox (macOS/Linux), or fail closed."""
    if sys.platform == "darwin":
        exe = shutil.which("sandbox-exec") or "/usr/bin/sandbox-exec"
        if not Path(exe).exists():
            raise SandboxUnavailableError("sandbox-exec tidak tersedia; eksekusi skrip ditolak (fail-closed).")
        return [exe, "-p", build_seatbelt_profile(workspace, read_roots), *cmd]

    if sys.platform.startswith("linux"):
        return build_linux_bwrap_args(workspace, read_roots, cmd)

    if sys.platform == "win32":
        # Windows does not use a CLI command wrapper; callers must use execute_in_os_sandbox()
        # which invokes AppContainer + suspended Job Object directly via Win32 API.
        raise SandboxUnavailableError(
            "Windows memerlukan launcher AppContainer API melalui execute_in_os_sandbox(); "
            "wrap_command() menolak mengembalikan command mentah (fail-closed)."
        )

    raise SandboxUnavailableError(
        f"Belum ada sandbox tingkat OS untuk platform '{sys.platform}'; eksekusi skrip ditolak (fail-closed)."
    )


async def execute_in_os_sandbox(
    cmd: list[str],
    cwd: Path,
    env: dict[str, str],
    workspace: Path,
    read_roots: list[Path] | None = None,
    timeout: float = 15.0,
    max_output_bytes: int = 1024 * 1024,
    *,
    required_read_roots: list[Path] | None = None,
    optional_read_roots: list[Path] | None = None,
) -> dict[str, Any]:
    """Unified OS-enforced sandboxed subprocess execution across macOS, Linux, and Windows."""
    if sys.platform == "win32":
        from app.skills.windows_sandbox import run_windows_appcontainer_sandboxed
        raw = await asyncio.to_thread(
            run_windows_appcontainer_sandboxed,
            cmd,
            cwd,
            env,
            workspace,
            read_roots,
            timeout,
            max_output_bytes,
            required_read_roots=required_read_roots,
            optional_read_roots=optional_read_roots,
        )
        return {
            "exit_code": raw["exit_code"],
            "stdout": raw["stdout"].decode("utf-8", errors="replace"),
            "stderr": raw["stderr"].decode("utf-8", errors="replace"),
        }

    combined_roots = [
        *(read_roots or []),
        *(required_read_roots or []),
        *(optional_read_roots or []),
    ]
    wrapped_cmd = wrap_command(cmd, workspace, combined_roots)
    proc = await asyncio.create_subprocess_exec(
        *wrapped_cmd,
        cwd=str(cwd),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "exit_code": proc.returncode,
            "stdout": stdout[:max_output_bytes].decode("utf-8", errors="replace"),
            "stderr": stderr[:max_output_bytes].decode("utf-8", errors="replace"),
        }
    except asyncio.TimeoutError:
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            await proc.wait()
        except Exception:
            pass
        raise TimeoutError(f"Eksekusi skrip sandbox melebihi batas waktu ({timeout}s).")
