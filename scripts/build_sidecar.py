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
import platform
import subprocess
import sys
from pathlib import Path


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


def build_sidecar(
    target_triple: str | None = None,
    dry_run: bool = False,
    one_file: bool = True,
) -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    engine_dir = repo_root / "services" / "engine"
    binaries_dir = repo_root / "apps" / "desktop" / "src-tauri" / "binaries"
    binaries_dir.mkdir(parents=True, exist_ok=True)

    triple = target_triple or detect_target_triple()
    ext = ".exe" if "windows" in triple or sys.platform == "win32" else ""
    target_binary_name = f"aksa-engine-{triple}{ext}"
    target_path = binaries_dir / target_binary_name

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
        "keyring",
        "keyring.backends",
        "cryptography",
        "openpyxl",
        "docx",
        "pptx",
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
        "--name",
        f"aksa-engine-{triple}",
        "--distpath",
        str(binaries_dir),
    ]

    if one_file:
        cmd.append("--onefile")

    for mod in hidden_imports:
        cmd.extend(["--hidden-import", mod])

    # Entry point
    entry_point = engine_dir / "app" / "main.py"
    cmd.append(str(entry_point))

    print(f"===============================================================")
    print(f"  AKSA Engine Sidecar Builder")
    print(f"  Target Triple : {triple}")
    print(f"  Target Binary : {target_path}")
    print(f"  Entry Point   : {entry_point}")
    print(f"===============================================================")

    if dry_run:
        print(f"[DRY-RUN] Command:\n{' '.join(cmd)}")
        return target_path

    # Verify PyInstaller is installed
    try:
        import PyInstaller  # type: ignore # noqa: F401
    except ImportError:
        print(f"ERROR: PyInstaller is not installed in the current environment ({sys.executable}).")
        print(f"Install it with: pip install pyinstaller")
        sys.exit(1)

    print(f"Running PyInstaller build...")
    subprocess.run(cmd, cwd=str(engine_dir), check=True)
    print(f"✅ Sidecar binary built successfully at: {target_path}")
    return target_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build AKSA Engine Sidecar binary for Tauri v2")
    parser.add_argument("--triple", type=str, default=None, help="Target triple (e.g. aarch64-apple-darwin)")
    parser.add_argument("--dry-run", action="store_true", help="Print PyInstaller command without building")
    parser.add_argument("--onedir", action="store_true", help="Build directory instead of single-file executable")

    args = parser.parse_args()
    build_sidecar(
        target_triple=args.triple,
        dry_run=args.dry_run,
        one_file=not args.onedir,
    )


if __name__ == "__main__":
    main()

