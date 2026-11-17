"""Cross-Platform One-Command Dev Runner for AKSA (Backend Engine + Desktop UI)."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ENGINE_DIR = ROOT_DIR / "services" / "engine"
DESKTOP_DIR = ROOT_DIR / "apps" / "desktop"


def _get_engine_python() -> str:
    if sys.platform == "win32":
        venv_py = ENGINE_DIR / ".venv" / "Scripts" / "python.exe"
    else:
        venv_py = ENGINE_DIR / ".venv" / "bin" / "python"
    return str(venv_py) if venv_py.exists() else sys.executable


def _stream_output(pipe: subprocess.Popen[str], prefix: str, color_code: str) -> None:
    assert pipe.stdout is not None
    reset = "\033[0m"
    for line in iter(pipe.stdout.readline, ""):
        if not line:
            break
        sys.stdout.write(f"{color_code}[{prefix}]{reset} {line}")
        sys.stdout.flush()


def _free_port(port: int) -> None:
    """Ensure port is not held by a dangling or previous engine instance."""
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return
        if sys.platform == "win32":
            subprocess.run(
                f'for /f "tokens=5" %a in (\'netstat -aon ^| findstr :{port}\') do taskkill /f /pid %a',
                shell=True,
                capture_output=True,
            )
        else:
            subprocess.run(f"lsof -ti :{port} | xargs kill -9", shell=True, capture_output=True)
    except Exception:
        pass


def main() -> int:
    use_tauri = "--tauri" in sys.argv
    check_only = "--check" in sys.argv

    _free_port(43120)

    cargo_bin = Path.home() / ".cargo" / "bin"
    if cargo_bin.exists() and str(cargo_bin) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{cargo_bin}:{os.environ.get('PATH', '')}"

    engine_py = _get_engine_python()
    engine_cmd = [
        engine_py,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "43120",
        "--reload",
    ]

    npm_bin = "npm.cmd" if sys.platform == "win32" else "npm"
    desktop_cmd = [npm_bin, "run", "tauri", "dev"] if use_tauri else [npm_bin, "run", "dev"]

    if check_only:
        print(f"Root Dir    : {ROOT_DIR}")
        print(f"Engine Cmd  : {' '.join(engine_cmd)} (cwd={ENGINE_DIR})")
        print(f"Desktop Cmd : {' '.join(desktop_cmd)} (cwd={DESKTOP_DIR})")
        return 0

    print("=================================================================")
    print("  AKSA — Menjalankan Backend Engine (43120) + Desktop UI (1420)")
    print("  Tekan Ctrl+C satu kali untuk menghentikan semua layanan.")
    print("=================================================================")

    procs: list[subprocess.Popen[str]] = []

    try:
        engine_proc = subprocess.Popen(
            engine_cmd,
            cwd=str(ENGINE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        procs.append(engine_proc)

        desktop_proc = subprocess.Popen(
            desktop_cmd,
            cwd=str(DESKTOP_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        procs.append(desktop_proc)

        t1 = threading.Thread(
            target=_stream_output, args=(engine_proc, "ENGINE ", "\033[36m"), daemon=True
        )
        t2 = threading.Thread(
            target=_stream_output, args=(desktop_proc, "DESKTOP", "\033[35m"), daemon=True
        )
        t1.start()
        t2.start()

        while all(p.poll() is None for p in procs):
            t1.join(timeout=0.3)
            t2.join(timeout=0.3)

    except KeyboardInterrupt:
        print("\nMenghentikan seluruh layanan AKSA...")
    finally:
        for p in procs:
            if p.poll() is None:
                try:
                    p.send_signal(signal.SIGTERM)
                except Exception:
                    p.terminate()
        for p in procs:
            try:
                p.wait(timeout=3)
            except Exception:
                p.kill()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

