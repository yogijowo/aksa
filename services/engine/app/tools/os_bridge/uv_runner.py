"""Tier 2 Self-Extending Python Script Runner via isolated `uv` or embedded venv."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from app.core.sandbox import RiskLevel, sandbox_manager
from app.core.token_optimizer import token_optimizer
from app.tools.registry import ToolResult, tool_registry


def _sync_run_custom_python_task(
    working_dir: str,
    script_code: str,
    required_packages: list[str] | None = None,
    timeout_seconds: int = 30,
) -> ToolResult:
    # Enforce both write and execute permissions on the workspace folder
    resolved_dir = sandbox_manager.validate_path(working_dir, mode="execute")
    resolved_dir.mkdir(parents=True, exist_ok=True)

    scripts_dir = resolved_dir / ".aksa_scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    script_file = scripts_dir / f"task_{uuid.uuid4().hex[:8]}.py"
    script_file.write_text(script_code, encoding="utf-8")

    # Track existing files to detect newly generated artifacts
    before_files = {
        p.resolve()
        for p in resolved_dir.iterdir()
        if p.is_file() and not p.name.startswith(".")
    }

    uv_bin = shutil.which("uv")
    pkgs = [p.strip() for p in (required_packages or []) if p.strip()]

    if uv_bin:
        cmd: list[str] = [uv_bin, "run", "--no-project"]
        for pkg in pkgs:
            cmd.extend(["--with", pkg])
        cmd.append(str(script_file))
        runner_used = "uv"
    else:
        cmd = [sys.executable, str(script_file)]
        runner_used = "python_venv"

    proc = subprocess.run(
        cmd,
        cwd=str(resolved_dir),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )

    after_files = {
        p.resolve()
        for p in resolved_dir.iterdir()
        if p.is_file() and not p.name.startswith(".")
    }
    created_artifacts = sorted(str(p) for p in (after_files - before_files))

    stdout_clean = (proc.stdout or "").strip()[:1500]
    stderr_clean = (proc.stderr or "").strip()[:1000]
    ok = proc.returncode == 0

    summary = (
        f"Eksekusi skrip Python mandiri ({runner_used}) {'berhasil' if ok else 'gagal'}. "
        f"Output: {stdout_clean[:200] or stderr_clean[:200] or 'Selesai tanpa output teks'}."
    )
    return ToolResult(
        success=ok,
        summary=summary,
        data={
            "runner": runner_used,
            "working_dir": str(resolved_dir),
            "script_path": str(script_file),
            "returncode": proc.returncode,
            "stdout": stdout_clean,
            "stderr": stderr_clean,
        },
        artifacts=created_artifacts,
        token_estimate=token_optimizer.estimate_tokens(summary + stdout_clean),
    )


async def run_custom_python_task(
    working_dir: str,
    script_code: str,
    required_packages: list[str] | None = None,
    timeout_seconds: int = 30,
) -> ToolResult:
    """Write and execute a custom Python script inside the authorized workspace directory."""
    return await asyncio.to_thread(
        _sync_run_custom_python_task,
        working_dir,
        script_code,
        required_packages,
        timeout_seconds,
    )


def register_uv_runner_tools() -> None:
    tool_registry.register(
        name="run_custom_python_task",
        category="uv_python",
        description="Tulis dan jalankan skrip Python kustom di dalam Folder Kerja menggunakan runtime terisolasi.",
        handler=run_custom_python_task,
        risk_level=RiskLevel.HIGH,
    )


register_uv_runner_tools()

