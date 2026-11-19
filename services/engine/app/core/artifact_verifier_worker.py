"""Killable Subprocess Worker for Bounded Artifact Postcondition Verification (Cycle 9 P2-03).

Executes document parsing and postcondition validation in an isolated child process so
a hard timeout terminates the parser via SIGKILL / TerminateProcess rather than leaving
an unkillable background thread running in the FastAPI/orchestrator process.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from pathlib import Path
from typing import Any

MAX_WORKER_STDIN_BYTES = 512 * 1024
MAX_WORKER_STDOUT_BYTES = 512 * 1024


def _verify_sync_in_subprocess(payload: dict[str, Any]) -> dict[str, Any]:
    from app.core.orchestrator import (
        MAX_ARTIFACT_VERIFY_BYTES,
        get_artifact_postcondition_breakdown,
        sanitize_verifier_schema,
    )

    art_raw = str(payload.get("artifact_path", "") or "").strip()
    ws_raw = str(payload.get("workspace", "") or "").strip()
    if not art_raw:
        return {"ok": False, "detail": "Path artefak worker kosong.", "breakdown": {}}

    art_path = Path(art_raw)
    if ws_raw:
        ws_real = Path(ws_raw).resolve(strict=False)
        try:
            resolved_art = art_path.resolve(strict=False)
        except Exception as exc:
            return {"ok": False, "detail": f"Gagal me-resolve path artefak: {exc}", "breakdown": {}}
        if art_path.is_symlink() or not resolved_art.is_relative_to(ws_real):
            return {"ok": False, "detail": "Artefak di luar workspace ditolak di worker verifikasi.", "breakdown": {}}

    schema = sanitize_verifier_schema(payload.get("expected_schema"))
    schema["max_bytes"] = MAX_ARTIFACT_VERIFY_BYTES if "expected_schema" not in payload else schema["max_bytes"]
    breakdown = get_artifact_postcondition_breakdown(art_path, expected_schema=schema)
    ok = bool(
        breakdown.get("file_created")
        and breakdown.get("format_valid")
        and breakdown.get("content_detected")
        and breakdown.get("task_requirement_satisfied")
        and breakdown.get("semantic_postcondition_passed")
        and not breakdown.get("unsupported_format")
    )
    return {"ok": ok, "detail": str(breakdown.get("detail", "")), "breakdown": breakdown}


def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    try:
        if sys.platform != "win32" and proc.pid:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGKILL)
            return
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass


async def verify_artifact_in_worker(
    art_path: Path,
    *,
    expected_schema: dict[str, Any] | None = None,
    workspace: Path | None = None,
    timeout: float = 10.0,
) -> tuple[bool, str]:
    """Run ``get_artifact_postcondition_breakdown`` inside a killable OS child process."""
    engine_root = str(Path(__file__).resolve().parent.parent.parent)
    allow_env_keys = (
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "VIRTUAL_ENV",
        "HOME",
        "TMPDIR",
        "TEMP",
        "TMP",
    )
    safe_env = {k: v for k, v in os.environ.items() if k in allow_env_keys}
    safe_env["PYTHONPATH"] = engine_root

    request_bytes = json.dumps(
        {
            "artifact_path": str(art_path),
            "workspace": str(workspace) if workspace is not None else "",
            "expected_schema": expected_schema or {},
        },
        ensure_ascii=False,
    ).encode("utf-8")

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.core.artifact_verifier_worker",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=safe_env,
        cwd=engine_root,
        start_new_session=(sys.platform != "win32"),
    )

    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(input=request_bytes),
            timeout=timeout,
        )
    except (asyncio.TimeoutError, TimeoutError):
        _kill_process_tree(proc)
        try:
            await proc.wait()
        except Exception:
            pass
        return False, f"Verifikasi artefak '{art_path.name}' dihentikan paksa (timeout {timeout}s)."

    if len(stdout_b) > MAX_WORKER_STDOUT_BYTES:
        return False, "Output worker verifikasi melebihi batas ukuran aman."
    if proc.returncode != 0:
        err_snip = stderr_b[:512].decode("utf-8", errors="replace").strip()
        return False, f"Worker verifikasi artefak gagal (exit={proc.returncode}): {err_snip}"

    try:
        parsed = json.loads(stdout_b.decode("utf-8"))
        return bool(parsed.get("ok")), str(parsed.get("detail", ""))
    except Exception as exc:
        return False, f"Respons worker verifikasi tidak valid: {exc}"


if __name__ == "__main__":
    raw = sys.stdin.buffer.read(MAX_WORKER_STDIN_BYTES + 1)
    if len(raw) > MAX_WORKER_STDIN_BYTES:
        sys.stdout.write(json.dumps({"ok": False, "detail": "Payload worker melebihi batas.", "breakdown": {}}))
        sys.exit(0)
    try:
        req = json.loads(raw.decode("utf-8"))
        out = _verify_sync_in_subprocess(req if isinstance(req, dict) else {})
    except Exception as exc:
        out = {"ok": False, "detail": f"Kesalahan internal worker verifikasi: {exc}", "breakdown": {}}
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    sys.stdout.flush()

