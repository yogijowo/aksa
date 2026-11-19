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

    raise SandboxUnavailableError(
        f"Belum ada sandbox tingkat OS untuk platform '{sys.platform}' (AppContainer/Job Object belum "
        "diimplementasikan); eksekusi skrip pihak ketiga ditolak (fail-closed)."
    )
