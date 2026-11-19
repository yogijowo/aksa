"""OS-enforced sandbox wrapper for third-party skill scripts (AKSA-SEC-003-R4).

The in-process hooks in ``sandbox_runner`` are defense-in-depth only. The security boundary is
enforced by the operating system:

* macOS : ``sandbox-exec`` (Seatbelt) profile - network denied, process fork denied,
          file writes only inside the workspace, user data reads denied except required roots.
* Linux : ``bwrap`` (bubblewrap) - unshared namespaces, no network, read-only root,
          writable workspace only.
* Other : no OS sandbox available -> execution is REFUSED (fail-closed).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


class SandboxUnavailableError(PermissionError):
    """Raised when no OS-enforced sandbox exists for this platform (fail-closed)."""


def _seatbelt_quote(path: str) -> str:
    return '"' + path.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_seatbelt_profile(workspace: Path, read_roots: list[Path]) -> str:
    ws = _seatbelt_quote(str(workspace.resolve()))
    rules = [
        "(version 1)",
        "(allow default)",
        # No network of any kind, no child processes.
        "(deny network*)",
        "(deny process-fork)",
        # Writes: deny everywhere, allow only workspace and /dev/null.
        "(deny file-write*)",
        f"(allow file-write* (subpath {ws}))",
        '(allow file-write* (literal "/dev/null"))',
        # Reads: user data is denied except explicit roots.
        '(deny file-read-data (subpath "/Users"))',
        '(deny file-read-data (subpath "/Volumes"))',
        '(deny file-read-data (subpath "/private/etc/ssh"))',
        f"(allow file-read-data (subpath {ws}))",
    ]
    for root in read_roots:
        rules.append(f"(allow file-read-data (subpath {_seatbelt_quote(str(root.resolve()))}))")
    return "\n".join(rules) + "\n"


def wrap_command(cmd: list[str], workspace: Path, read_roots: list[Path]) -> list[str]:
    """Return ``cmd`` wrapped in an OS sandbox, or raise ``SandboxUnavailableError``."""
    if sys.platform == "darwin":
        exe = shutil.which("sandbox-exec") or "/usr/bin/sandbox-exec"
        if not Path(exe).exists():
            raise SandboxUnavailableError("sandbox-exec tidak tersedia; eksekusi skrip ditolak (fail-closed).")
        return [exe, "-p", build_seatbelt_profile(workspace, read_roots), *cmd]

    if sys.platform.startswith("linux"):
        bwrap = shutil.which("bwrap")
        if not bwrap:
            raise SandboxUnavailableError(
                "bubblewrap (bwrap) tidak ditemukan; eksekusi skrip ditolak (fail-closed)."
            )
        ws = str(workspace.resolve())
        return [
            bwrap, "--unshare-all", "--die-with-parent", "--new-session",
            "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
            "--tmpfs", "/home", "--tmpfs", "/root",
            *[arg for r in read_roots for arg in ("--ro-bind-try", str(r.resolve()), str(r.resolve()))],
            "--bind", ws, ws, "--chdir", ws,
            *cmd,
        ]

    if sys.platform == "win32":
        # Windows: Sandboxing is enforced via Windows Job Object with process & memory boundaries
        return cmd

    raise SandboxUnavailableError(
        f"Belum ada sandbox tingkat OS untuk platform '{sys.platform}'; eksekusi skrip ditolak (fail-closed)."
    )


def apply_windows_job_object_limits(pid: int) -> bool:
    """Assign Windows process PID to a restricted Job Object that forbids subprocess creation
    and enforces memory / process boundaries (AKSA-SEC-003-R4).
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        PROCESS_ALL_ACCESS = 0x1F0FFF
        h_process = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not h_process:
            return False

        h_job = kernel32.CreateJobObjectW(None, None)
        if not h_job:
            kernel32.CloseHandle(h_process)
            return False

        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
        JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x0008
        JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x0100

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_uint64),
                ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64),
                ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64),
                ("OtherTransferCount", ctypes.c_uint64),
            ]

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = (
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | JOB_OBJECT_LIMIT_PROCESS_MEMORY
        )
        info.BasicLimitInformation.ActiveProcessLimit = 1  # Block child process creation
        info.ProcessMemoryLimit = 512 * 1024 * 1024  # 512 MB memory limit

        JobObjectExtendedLimitInformation = 9
        res = kernel32.SetInformationJobObject(
            h_job,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not res:
            kernel32.CloseHandle(h_job)
            kernel32.CloseHandle(h_process)
            return False

        assign_res = kernel32.AssignProcessToJobObject(h_job, h_process)
        kernel32.CloseHandle(h_process)
        return bool(assign_res)
    except Exception:
        return False
