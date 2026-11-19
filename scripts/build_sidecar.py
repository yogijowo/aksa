#!/usr/bin/env python3
"""Cross-Platform Sidecar Binary Builder for AKSA Engine.

Freezes `services/engine` into a standalone native binary per target triple:
  - aarch64-apple-darwin (Apple Silicon macOS)
  - x86_64-apple-darwin (Intel macOS)
  - x86_64-pc-windows-msvc (Windows 64-bit)

Outputs to: `apps/desktop/src-tauri/binaries/aksa-engine-<target-triple>[.exe]`
"""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

MIN_REAL_SIDECAR_BYTES = 1_000_000


def detect_target_triple() -> str:
    """Detect current system's target triple matching Rust/Tauri conventions."""
    try:
        out = subprocess.check_output(["rustc", "-vV"], text=True, timeout=5)
        for line in out.splitlines():
            if line.startswith("host:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass

    machine = platform.machine().lower()
    if sys.platform == "win32":
        return "x86_64-pc-windows-msvc"
    if sys.platform == "darwin":
        return "aarch64-apple-darwin" if "arm" in machine or "aarch64" in machine else "x86_64-apple-darwin"
    return "x86_64-unknown-linux-gnu"


def resolve_sidecar_binary_path(target_triple: str | None = None) -> Path:
    """Resolve the expected Tauri target-triple sidecar binary path."""
    repo_root = Path(__file__).resolve().parent.parent
    binaries_dir = repo_root / "apps" / "desktop" / "src-tauri" / "binaries"
    binaries_dir.mkdir(parents=True, exist_ok=True)
    triple = target_triple or detect_target_triple()
    ext = ".exe" if "windows" in triple or (target_triple is None and sys.platform == "win32") else ""
    return binaries_dir / f"aksa-engine-{triple}{ext}"


def verify_sidecar_binary(
    target_path: Path,
    *,
    min_size_bytes: int = MIN_REAL_SIDECAR_BYTES,
) -> Path:
    """Verify the target-triple sidecar binary exists, is executable, and is not a stub/dummy."""
    if not target_path.exists() or target_path.is_symlink() or not target_path.is_file():
        raise FileNotFoundError(
            f"Binary sidecar target-triple tidak ditemukan atau bukan file reguler: {target_path}"
        )
    size_bytes = target_path.stat().st_size
    if size_bytes < min_size_bytes:
        raise RuntimeError(
            f"Ukuran binary sidecar '{target_path}' terlalu kecil ({size_bytes} bytes < {min_size_bytes}); "
            "wrapper/dummy kosong ditolak untuk build & Cargo check."
        )
    if sys.platform != "win32":
        mode = target_path.stat().st_mode
        if not (mode & 0o111):
            target_path.chmod(mode | 0o755)
        if not os.access(target_path, os.X_OK):
            raise PermissionError(f"Binary sidecar tidak memiliki izin eksekusi: {target_path}")
    print(f"✅ Sidecar verified: {target_path} ({size_bytes:,} bytes, executable)")
    return target_path


def build_sidecar(
    target_triple: str | None = None,
    dry_run: bool = False,
    one_file: bool = True,
    verify: bool = True,
) -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    engine_dir = repo_root / "services" / "engine"
    binaries_dir = repo_root / "apps" / "desktop" / "src-tauri" / "binaries"
    binaries_dir.mkdir(parents=True, exist_ok=True)
    work_dir = repo_root / "build" / "pyinstaller-work"
    spec_dir = repo_root / "build" / "pyinstaller-spec"

    triple = target_triple or detect_target_triple()
    target_path = resolve_sidecar_binary_path(triple)

    hidden_imports = [
        "aiosqlite",
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "websockets",
        "fastapi",
        "starlette",
        "pydantic",
        "pydantic_settings",
        "httpx",
        "keyring",
        "keyring.backends",
        "cryptography",
        "jsonschema",
        "numpy",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "openpyxl",
        "docx",
        "pptx",
        "pymupdf",
        "fitz",
        "reportlab",
        "watchdog",
        "aiogram",
    ]

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--paths",
        str(engine_dir),
        "--collect-submodules",
        "app",
        "--collect-submodules",
        "keyring.backends",
        "--name",
        f"aksa-engine-{triple}",
        "--distpath",
        str(binaries_dir),
        "--workpath",
        str(work_dir / triple),
        "--specpath",
        str(spec_dir),
    ]

    if one_file:
        cmd.append("--onefile")

    for mod in hidden_imports:
        cmd.extend(["--hidden-import", mod])

    # Entry point
    entry_point = engine_dir / "app" / "main.py"
    cmd.append(str(entry_point))

    print("===============================================================")
    print("  AKSA Engine Sidecar Builder")
    print(f"  Target Triple : {triple}")
    print(f"  Target Binary : {target_path}")
    print(f"  Entry Point   : {entry_point}")
    print("===============================================================")

    if dry_run:
        print(f"[DRY-RUN] Command:\n{' '.join(cmd)}")
        return target_path

    # Verify PyInstaller is installed
    try:
        import PyInstaller  # type: ignore # noqa: F401
    except ImportError:
        print(f"ERROR: PyInstaller is not installed in the current environment ({sys.executable}).")
        print("Install it with: pip install pyinstaller")
        sys.exit(1)

    work_dir.mkdir(parents=True, exist_ok=True)
    spec_dir.mkdir(parents=True, exist_ok=True)
    print("Running PyInstaller build...")
    subprocess.run(cmd, cwd=str(engine_dir), check=True)
    print(f"✅ Sidecar binary built successfully at: {target_path}")
    if verify:
        verify_sidecar_binary(target_path)
    return target_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build AKSA Engine Sidecar binary for Tauri v2")
    parser.add_argument("--triple", type=str, default=None, help="Target triple (e.g. aarch64-apple-darwin)")
    parser.add_argument("--dry-run", action="store_true", help="Print PyInstaller command without building")
    parser.add_argument("--onedir", action="store_true", help="Build directory instead of single-file executable")
    parser.add_argument("--verify-only", action="store_true", help="Verify existing target-triple sidecar binary")

    args = parser.parse_args()
    if args.verify_only:
        path = resolve_sidecar_binary_path(args.triple)
        try:
            verify_sidecar_binary(path)
        except Exception as exc:
            print(f"❌ Sidecar verification failed: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    build_sidecar(
        target_triple=args.triple,
        dry_run=args.dry_run,
        one_file=not args.onedir,
    )


if __name__ == "__main__":
    main()

