"""Hardened OS and Python Runtime Sandbox Runner for Skill Execution (AKSA-SEC-003-R3).

Enforces:
1. Static AST pre-execution scan (blocks dangerous modules, dynamic imports, eval, environment scraping).
2. Runtime Dynamic Import Interception: builtins.__import__ and importlib.import_module hook.
3. Complete Network Interception: poisons socket, _socket, urllib, requests, http modules.
4. Comprehensive Filesystem Path Jail:
   - builtins.open, io.open, _io.open, os.open
   - pathlib.Path.read_text, write_text, open
   - os.replace, os.rename, os.remove, os.unlink, os.mkdir, os.rmdir, os.chmod, os.link, os.symlink
5. OS-level resource limits: RLIMIT_NPROC=0, RLIMIT_FSIZE=50MB, RLIMIT_CPU=15s, RLIMIT_AS=512MB.
6. Subprocess and fork interception.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import io
import json
import os
from pathlib import Path
import runpy
import sys
from typing import Any

# Dangerous AST identifiers and modules
FORBIDDEN_CALLS = {"eval", "exec", "compile"}
FORBIDDEN_MODULES = {
    "socket",
    "_socket",
    "importlib",
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
    "_posixsubprocess",
    "_winapi",
    "code",
    "pdb",
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

# Runtime blocked modules for dynamic import interception (builtins.__import__ & importlib.import_module)
DANGEROUS_RUNTIME_MODULES = {
    "socket",
    "_socket",
    "urllib",
    "http",
    "requests",
    "httpx",
    "aiohttp",
    "subprocess",
    "ctypes",
    "pty",
    "multiprocessing",
    "winreg",
    "webbrowser",
    "_posixsubprocess",
    "_winapi",
    "code",
    "pdb",
}

# AKSA-SEC-003-R4: introspection attributes that allow recovering original (un-hooked) functions
# from closures, frames, generators, or builtins regardless of the receiver expression.
FORBIDDEN_INTROSPECTION_ATTRS = {
    "__closure__", "cell_contents", "__globals__", "__code__", "__builtins__",
    "__wrapped__", "__self__", "__func__", "__getattribute__", "__subclasses__",
    "__mro__", "__bases__", "__base__", "__dict__", "__loader__", "__spec__",
    "gi_frame", "gi_code", "cr_frame", "cr_code", "ag_frame", "f_globals",
    "f_locals", "f_builtins", "f_back", "tb_frame", "co_code", "__reduce__",
    "__reduce_ex__", "__import__",
}
FORBIDDEN_INTROSPECTION_CALLS = {"getattr", "setattr", "delattr", "vars", "globals", "locals", "breakpoint", "memoryview"}


def scan_ast_security(script_content: str, filename: str = "<script>") -> None:
    """Perform static AST inspection of script content before execution (AKSA-SEC-003-R3)."""
    try:
        tree = ast.parse(script_content, filename=filename)
    except SyntaxError as exc:
        raise ValueError(f"Sintaks skrip tidak valid: {exc}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in FORBIDDEN_INTROSPECTION_ATTRS:
            raise PermissionError(f"Literal introspeksi '{node.value}' dilarang oleh Sandbox AKSA.")
        # 1. Direct function calls to eval, exec, compile
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                raise PermissionError(f"Penggunaan fungsi dinamis '{node.func.id}()' dilarang oleh Sandbox AKSA.")
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_INTROSPECTION_CALLS:
                raise PermissionError(f"Penggunaan fungsi introspeksi '{node.func.id}()' dilarang oleh Sandbox AKSA.")
            # Detect __import__ calls
            if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                raise PermissionError("Penggunaan '__import__()' dinamis dilarang oleh Sandbox AKSA.")

        # 2. Imports of network, subprocess, ctypes, importlib modules
        elif isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if mod in FORBIDDEN_MODULES or alias.name in FORBIDDEN_MODULES:
                    raise PermissionError(f"Impor modul berisiko tinggi '{alias.name}' dilarang oleh Sandbox AKSA.")

        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0]
            if mod in FORBIDDEN_MODULES or node.module in FORBIDDEN_MODULES:
                raise PermissionError(f"Impor modul berisiko tinggi '{node.module}' dilarang oleh Sandbox AKSA.")

        # 3a. Introspection attributes (closure / frame / globals recovery) on ANY receiver
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_INTROSPECTION_ATTRS:
            raise PermissionError(f"Akses atribut introspeksi '{node.attr}' dilarang oleh Sandbox AKSA.")

        # 3. Attribute access to os.environ, os.system, sys.modules
        elif isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_ATTRIBUTES:
                if isinstance(node.value, ast.Name) and node.value.id in ("os", "sys"):
                    raise PermissionError(f"Akses atribut sistem '{node.value.id}.{node.attr}' dilarang oleh Sandbox AKSA.")


def apply_runtime_sandbox(workspace_path: Path, script_path: Path) -> None:
    """Apply exhaustive in-process filesystem jail, dynamic import hooks, and network interception."""
    canonical_ws = Path(os.path.realpath(os.path.expanduser(str(workspace_path))))
    script_dir = Path(os.path.realpath(os.path.expanduser(str(script_path.parent))))

    # Allowed read roots: workspace, script directory, python runtime & stdlib
    allowed_read_roots = [
        canonical_ws,
        script_dir,
        Path(os.path.realpath(sys.prefix)),
        Path(os.path.realpath(sys.base_prefix)),
    ]

    def _is_safe_read(p: Any) -> bool:
        try:
            target = Path(os.path.realpath(os.path.expanduser(str(p))))
        except Exception:
            return False
        return any(target == r or target.is_relative_to(r) for r in allowed_read_roots)

    def _is_safe_write(p: Any) -> bool:
        try:
            target = Path(os.path.realpath(os.path.expanduser(str(p))))
        except Exception:
            return False
        return target == canonical_ws or target.is_relative_to(canonical_ws)

    # 1. OS Resource Limits (POSIX)
    try:
        import resource
        if hasattr(resource, "RLIMIT_NPROC"):
            try:
                resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
            except Exception:
                pass
        if hasattr(resource, "RLIMIT_FSIZE"):
            try:
                resource.setrlimit(resource.RLIMIT_FSIZE, (50 * 1024 * 1024, 50 * 1024 * 1024))
            except Exception:
                pass
        if hasattr(resource, "RLIMIT_CPU"):
            try:
                resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
            except Exception:
                pass
        if hasattr(resource, "RLIMIT_AS"):
            try:
                resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
            except Exception:
                pass
    except Exception:
        pass

    # 2. Block Dynamic Imports (builtins.__import__ & importlib.import_module)
    orig_builtin_import = builtins.__import__

    def sandboxed_import(name: str, globals: Any = None, locals: Any = None, fromlist: Any = (), level: int = 0) -> Any:
        mod_root = name.split(".")[0]
        if mod_root in DANGEROUS_RUNTIME_MODULES or name in DANGEROUS_RUNTIME_MODULES:
            raise PermissionError(f"Impor modul berisiko tinggi '{name}' dilarang oleh Sandbox AKSA.")
        if fromlist:
            for item in fromlist:
                if item in DANGEROUS_RUNTIME_MODULES or f"{name}.{item}" in DANGEROUS_RUNTIME_MODULES:
                    raise PermissionError(f"Impor sub-modul berisiko tinggi '{name}.{item}' dilarang oleh Sandbox AKSA.")
        return orig_builtin_import(name, globals, locals, fromlist, level)

    builtins.__import__ = sandboxed_import

    try:
        import importlib
        orig_import_module = importlib.import_module

        def sandboxed_import_module(name: str, package: Any = None) -> Any:
            mod_root = name.split(".")[0]
            if mod_root in DANGEROUS_RUNTIME_MODULES or name in DANGEROUS_RUNTIME_MODULES:
                raise PermissionError(f"Impor dinamis modul berisiko tinggi '{name}' dilarang oleh Sandbox AKSA.")
            return orig_import_module(name, package=package)

        importlib.import_module = sandboxed_import_module
    except Exception:
        pass

    # 3. Block Network Sockets Completely
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
    for mod_name in ("_socket", "socket", "urllib", "urllib.request", "http", "http.client", "requests", "httpx", "aiohttp"):
        sys.modules[mod_name] = None  # type: ignore[assignment]

    # 4. Block Subprocesses and External Execution
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

    # 5. Exhaustive Filesystem Path Jail Interception (builtins.open, io.open, os.open)
    def _make_sandboxed_open(orig_fn: Any) -> Any:
        def sandboxed_open_fn(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
            if isinstance(file, int):
                return orig_fn(file, mode, *args, **kwargs)
            is_write = any(m in mode for m in ("w", "a", "+", "x"))
            if is_write:
                if not _is_safe_write(file):
                    raise PermissionError(
                        f"Akses ditolak oleh Sandbox AKSA: Penulisan ke file '{file}' di luar folder kerja dilarang."
                    )
            else:
                if not _is_safe_read(file):
                    raise PermissionError(
                        f"Akses ditolak oleh Sandbox AKSA: Pembacaan file '{file}' di luar folder kerja dilarang."
                    )
            return orig_fn(file, mode, *args, **kwargs)
        return sandboxed_open_fn

    orig_builtin_open = builtins.open
    builtins.open = _make_sandboxed_open(orig_builtin_open)
    io.open = _make_sandboxed_open(io.open)

    try:
        import _io
        if hasattr(_io, "open"):
            _io.open = _make_sandboxed_open(_io.open)
    except Exception:
        pass

    # Low-level os.open hook
    orig_os_open = os.open

    def sandboxed_os_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        is_write = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | getattr(os, "O_APPEND", 0)))
        if is_write:
            if not _is_safe_write(path):
                raise PermissionError(
                    f"Akses ditolak oleh Sandbox AKSA: os.open penulisan ke '{path}' di luar folder kerja dilarang."
                )
        else:
            if not _is_safe_read(path):
                raise PermissionError(
                    f"Akses ditolak oleh Sandbox AKSA: os.open pembacaan '{path}' di luar folder kerja dilarang."
                )
        return orig_os_open(path, flags, *args, **kwargs)

    os.open = sandboxed_os_open

    # Mutating os operations hooks
    def _require_safe_write(p: Any, op_name: str) -> None:
        if not _is_safe_write(p):
            raise PermissionError(f"Akses ditolak oleh Sandbox AKSA: {op_name} pada '{p}' di luar folder kerja dilarang.")

    orig_remove = os.remove
    orig_unlink = os.unlink
    orig_mkdir = os.mkdir
    orig_rmdir = os.rmdir
    orig_rename = os.rename
    orig_replace = os.replace

    os.remove = lambda p, *a, **k: (_require_safe_write(p, "os.remove"), orig_remove(p, *a, **k))[1]
    os.unlink = lambda p, *a, **k: (_require_safe_write(p, "os.unlink"), orig_unlink(p, *a, **k))[1]
    os.mkdir = lambda p, *a, **k: (_require_safe_write(p, "os.mkdir"), orig_mkdir(p, *a, **k))[1]
    os.rmdir = lambda p, *a, **k: (_require_safe_write(p, "os.rmdir"), orig_rmdir(p, *a, **k))[1]
    os.rename = lambda src, dst, *a, **k: (_require_safe_write(src, "os.rename src"), _require_safe_write(dst, "os.rename dst"), orig_rename(src, dst, *a, **k))[2]
    os.replace = lambda src, dst, *a, **k: (_require_safe_write(src, "os.replace src"), _require_safe_write(dst, "os.replace dst"), orig_replace(src, dst, *a, **k))[2]

    if hasattr(os, "symlink"):
        orig_symlink = os.symlink

        def sandboxed_symlink(src: Any, dst: Any, *a: Any, **k: Any) -> Any:
            _require_safe_write(dst, "os.symlink dest")
            if not _is_safe_read(src):
                raise PermissionError(f"Akses ditolak oleh Sandbox AKSA: os.symlink target '{src}' di luar batas aman.")
            return orig_symlink(src, dst, *a, **k)

        os.symlink = sandboxed_symlink

    if hasattr(os, "link"):
        orig_link = os.link
        os.link = lambda src, dst, *a, **k: (_require_safe_write(src, "os.link src"), _require_safe_write(dst, "os.link dst"), orig_link(src, dst, *a, **k))[2]

    if hasattr(os, "chmod"):
        orig_chmod = os.chmod
        os.chmod = lambda p, m, *a, **k: (_require_safe_write(p, "os.chmod"), orig_chmod(p, m, *a, **k))[1]


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
