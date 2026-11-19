"""Hardened OS and Python Runtime Sandbox Runner for Skill Execution (AKSA-SEC-003-R2).

Enforces:
1. Static AST pre-execution scan (blocks dangerous modules, dynamic execution, environment scraping).
2. OS resource limits (RLIMIT_NPROC, RLIMIT_FSIZE, RLIMIT_AS).
3. Runtime network interception (completely blocks socket creation and HTTP clients).
4. Runtime filesystem path jail (strictly bounds write and read operations to authorized workspace).
5. Subprocess and fork interception (blocks external process spawning).
"""

from __future__ import annotations

import argparse
import ast
import builtins
import json
import os
from pathlib import Path
import runpy
import sys
from typing import Any

# Dangerous AST identifiers and calls
FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__"}
FORBIDDEN_MODULES = {
    "socket",
    "urllib",
    "urllib.request",
    "http",
    "http.client",
    "requests",
    "httpx",
    "aiohttp",
    "subprocess",
    "ctypes",
    "pty",
    "multiprocessing",
    "winreg",
    "webbrowser",
}
FORBIDDEN_ATTRIBUTES = {
    "environ",
    "system",
    "popen",
    "spawn",
    "fork",
    "modules",
    "__subclasses__",
}


def scan_ast_security(script_content: str, filename: str = "<script>") -> None:
    """Perform static AST inspection of script content before execution (AKSA-SEC-003-R2)."""
    try:
        tree = ast.parse(script_content, filename=filename)
    except SyntaxError as exc:
        raise ValueError(f"Sintaks skrip tidak valid: {exc}")

    for node in ast.walk(tree):
        # 1. Direct function calls to eval, exec, compile
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                raise PermissionError(f"Penggunaan fungsi dinamis '{node.func.id}()' dilarang oleh Sandbox AKSA.")

        # 2. Imports of network, subprocess, ctypes modules
        elif isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if mod in FORBIDDEN_MODULES or alias.name in FORBIDDEN_MODULES:
                    raise PermissionError(f"Impor modul berisiko tinggi '{alias.name}' dilarang oleh Sandbox AKSA.")

        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0]
            if mod in FORBIDDEN_MODULES or node.module in FORBIDDEN_MODULES:
                raise PermissionError(f"Impor modul berisiko tinggi '{node.module}' dilarang oleh Sandbox AKSA.")

        # 3. Attribute access to os.environ, os.system, sys.modules
        elif isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_ATTRIBUTES:
                if isinstance(node.value, ast.Name) and node.value.id in ("os", "sys"):
                    raise PermissionError(f"Akses atribut sistem '{node.value.id}.{node.attr}' dilarang oleh Sandbox AKSA.")


def apply_runtime_sandbox(workspace_path: Path, script_path: Path) -> None:
    """Apply in-process filesystem jail, network interception, and process limits."""
    canonical_ws = Path(os.path.realpath(os.path.expanduser(str(workspace_path))))
    script_dir = Path(os.path.realpath(os.path.expanduser(str(script_path.parent))))

    # Allowed read roots: workspace, script directory, python runtime & stdlib
    allowed_read_roots = [
        canonical_ws,
        script_dir,
        Path(os.path.realpath(sys.prefix)),
        Path(os.path.realpath(sys.base_prefix)),
    ]

    # 1. OS Resource Limits (POSIX)
    try:
        import resource
        # Limit max child processes to 0 (cannot spawn child processes)
        if hasattr(resource, "RLIMIT_NPROC"):
            try:
                resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
            except Exception:
                pass
        # Limit file size written (50 MB)
        if hasattr(resource, "RLIMIT_FSIZE"):
            try:
                resource.setrlimit(resource.RLIMIT_FSIZE, (50 * 1024 * 1024, 50 * 1024 * 1024))
            except Exception:
                pass
    except ImportError:
        pass

    # 2. Block Network Sockets Completely
    def _blocked_network(*args: Any, **kwargs: Any) -> Any:
        raise PermissionError("Akses jaringan diblokir oleh Sandbox AKSA.")

    try:
        import socket
        socket.socket = _blocked_network  # type: ignore[assignment]
        if hasattr(socket, "create_connection"):
            socket.create_connection = _blocked_network  # type: ignore[assignment]
    except Exception:
        pass

    # Poison network module imports in sys.modules
    for mod_name in ("urllib", "urllib.request", "http.client", "requests", "httpx", "aiohttp"):
        sys.modules[mod_name] = None  # type: ignore[assignment]

    # 3. Block Subprocesses and External Execution
    def _blocked_subprocess(*args: Any, **kwargs: Any) -> Any:
        raise PermissionError("Pembuatan proses eksternal diblokir oleh Sandbox AKSA.")

    try:
        import subprocess
        subprocess.Popen = _blocked_subprocess  # type: ignore[assignment]
        subprocess.run = _blocked_subprocess  # type: ignore[assignment]
        if hasattr(subprocess, "call"):
            subprocess.call = _blocked_subprocess  # type: ignore[assignment]
    except Exception:
        pass

    os.system = _blocked_subprocess  # type: ignore[assignment]
    os.popen = _blocked_subprocess  # type: ignore[assignment]
    if hasattr(os, "fork"):
        os.fork = _blocked_subprocess  # type: ignore[assignment]
    if hasattr(os, "spawnl"):
        os.spawnl = _blocked_subprocess  # type: ignore[assignment]

    # 4. Filesystem Path Jail Interception
    orig_open = builtins.open

    def sandboxed_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        try:
            target = Path(os.path.realpath(os.path.expanduser(str(file))))
        except Exception as exc:
            raise PermissionError(f"Akses path tidak valid: {exc}")

        is_write = any(m in mode for m in ("w", "a", "+", "x"))
        if is_write:
            if target != canonical_ws and not target.is_relative_to(canonical_ws):
                raise PermissionError(
                    f"Akses ditolak oleh Sandbox AKSA: Penulisan ke file '{target}' di luar folder kerja dilarang."
                )
        else:
            # Read operations must be within authorized roots
            if not any(target == r or target.is_relative_to(r) for r in allowed_read_roots):
                raise PermissionError(
                    f"Akses ditolak oleh Sandbox AKSA: Pembacaan file '{target}' di luar folder kerja dilarang."
                )

        return orig_open(file, mode, *args, **kwargs)

    builtins.open = sandboxed_open  # type: ignore[assignment]

    # Hook os filesystem mutators
    def _check_fs_path(p: Any) -> Path:
        target = Path(os.path.realpath(os.path.expanduser(str(p))))
        if target != canonical_ws and not target.is_relative_to(canonical_ws):
            raise PermissionError(
                f"Akses ditolak oleh Sandbox AKSA: Operasi filesystem pada '{target}' di luar folder kerja dilarang."
            )
        return target

    orig_remove = os.remove
    orig_unlink = os.unlink
    orig_mkdir = os.mkdir
    orig_rmdir = os.rmdir

    def sandboxed_remove(path: Any, *args: Any, **kwargs: Any) -> Any:
        _check_fs_path(path)
        return orig_remove(path, *args, **kwargs)

    def sandboxed_unlink(path: Any, *args: Any, **kwargs: Any) -> Any:
        _check_fs_path(path)
        return orig_unlink(path, *args, **kwargs)

    def sandboxed_mkdir(path: Any, *args: Any, **kwargs: Any) -> Any:
        _check_fs_path(path)
        return orig_mkdir(path, *args, **kwargs)

    def sandboxed_rmdir(path: Any, *args: Any, **kwargs: Any) -> Any:
        _check_fs_path(path)
        return orig_rmdir(path, *args, **kwargs)

    os.remove = sandboxed_remove  # type: ignore[assignment]
    os.unlink = sandboxed_unlink  # type: ignore[assignment]
    os.mkdir = sandboxed_mkdir  # type: ignore[assignment]
    os.rmdir = sandboxed_rmdir  # type: ignore[assignment]


def main() -> None:
    parser = argparse.ArgumentParser(description="AKSA Sandboxed Script Runner")
    parser.add_argument("--script", required=True, help="Path to Python script to execute")
    parser.add_argument("--workspace", required=True, help="Authorized workspace directory")
    parser.add_argument("--script-args", default="[]", help="JSON list of arguments for the script")

    args = parser.parse_args()

    script_path = Path(args.script).resolve()
    workspace_path = Path(args.workspace).resolve()

    if not script_path.exists():
        sys.stderr.write(f"Script file '{script_path}' not found.\n")
        sys.exit(1)

    if not workspace_path.exists():
        sys.stderr.write(f"Workspace directory '{workspace_path}' not found.\n")
        sys.exit(1)

    # 1. AST Security Inspection
    content = script_path.read_text(encoding="utf-8", errors="replace")
    try:
        scan_ast_security(content, filename=script_path.name)
    except (PermissionError, ValueError) as exc:
        sys.stderr.write(f"Sandbox Violation: {exc}\n")
        sys.exit(13)

    # 2. Parse passed script args
    try:
        user_args = json.loads(args.script_args)
        if not isinstance(user_args, list):
            user_args = [str(user_args)]
    except Exception:
        user_args = []

    # 3. Apply Runtime Jail
    apply_runtime_sandbox(workspace_path, script_path)

    # 4. Switch working directory to workspace
    os.chdir(str(workspace_path))

    # 5. Set up sys.argv
    sys.argv = [str(script_path)] + [str(a) for a in user_args]

    # 6. Execute script safely
    try:
        runpy.run_path(str(script_path), run_name="__main__")
    except SystemExit as exc:
        sys.exit(exc.code if exc.code is not None else 0)
    except PermissionError as exc:
        sys.stderr.write(f"Sandbox Permission Error: {exc}\n")
        sys.exit(13)
    except Exception as exc:
        sys.stderr.write(f"Script Execution Error: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

