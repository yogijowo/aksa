"""Cross-Platform PyInstaller Sidecar Builder for Tauri v2 (`aksa-engine-<target-triple>`)."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path


def detect_rustc_target_triple() -> str:
    """Detect the current platform's Rust/Tauri target triple."""
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


def build_sidecar(dry_run: bool = False) -> Path:
    """Bundle `services/engine/app/main.py` into `apps/desktop/src-tauri/binaries/aksa-engine-<triple>`."""
    engine_dir = Path(__file__).resolve().parent.parent
    repo_root = engine_dir.parent.parent
    binaries_dir = repo_root / "apps" / "desktop" / "src-tauri" / "binaries"
    binaries_dir.mkdir(parents=True, exist_ok=True)

    triple = detect_rustc_target_triple()
    ext = ".exe" if sys.platform == "win32" else ""
    binary_name = f"aksa-engine-{triple}{ext}"
    target_binary_path = binaries_dir / binary_name

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--name",
        f"aksa-engine-{triple}",
        "--distpath",
        str(binaries_dir),
        str(engine_dir / "app" / "main.py"),
    ]

    if dry_run:
        print(f"[DRY-RUN] Target sidecar binary: {target_binary_path}")
        print(f"[DRY-RUN] Command: {' '.join(cmd)}")
        return target_binary_path

    subprocess.run(cmd, cwd=str(engine_dir), check=True)
    return target_binary_path


if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    output = build_sidecar(dry_run=is_dry)
    print(f"Sidecar target ready: {output}")

