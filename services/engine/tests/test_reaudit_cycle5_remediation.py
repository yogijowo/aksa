"""Cycle 5 remediation tests (AKSA-SEC-003-R4, SEC-004-R4, SKILL-002-R4, SEC-002-R4, SEC-001-R4)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.db.models import db_manager
from app.skills.os_sandbox import SandboxUnavailableError, wrap_command
from app.skills.sandbox_runner import scan_ast_security
from app.skills.skill_manager import PublisherTrustStore, agent_skills_manager
from app.tools.mcp.mcp_client import MCPServerConfig, check_mcp_server_permissions

ENGINE_ROOT = Path(__file__).resolve().parent.parent
darwin_only = pytest.mark.skipif(sys.platform != "darwin", reason="Seatbelt sandbox is macOS-only")


# ---- SEC-003-R4: introspection bypass vectors -------------------------------------------------

@pytest.mark.parametrize("snippet", [
    "import os\nfor c in (os.open.__closure__ or ()):\n    print(c.cell_contents)\n",
    "import os\nf = os.open.__globals__\n",
    "x = (lambda: 1).__code__\n",
    "import os\ngetattr(os, 'op' + 'en')\n",
    "g = globals()\n",
    "(i for i in []).gi_frame.f_back\n",
    "print(type(1).__subclasses__)\n",
    "import os\nos.open.__wrapped__\n",
])
def test_ast_blocks_closure_and_introspection_vectors(snippet: str):
    with pytest.raises(PermissionError):
        scan_ast_security(snippet)


# ---- SEC-003-R4: OS-enforced boundary, proven WITHOUT the in-process hooks --------------------

def _run_sandboxed_raw(tmp_path: Path, code: str) -> subprocess.CompletedProcess:
    ws = tmp_path / "ws"
    ws.mkdir(exist_ok=True)
    script = ws / "raw.py"
    script.write_text(code, encoding="utf-8")
    roots = [Path(sys.prefix), Path(sys.base_prefix), Path(sys.executable).resolve().parent, ws]
    cmd = wrap_command([sys.executable, str(script)], ws, roots)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ws, env={"PATH": "/usr/bin"}, timeout=30)


@darwin_only
def test_os_sandbox_denies_network_without_python_hooks(tmp_path: Path):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        res = _run_sandboxed_raw(tmp_path, (
            "import socket,sys\n"
            f"s=socket.socket()\ntry:\n    s.connect(('127.0.0.1',{port}))\n    print('CONNECTED')\n"
            "except OSError as e:\n    print('DENIED', e)\n"
        ))
    finally:
        srv.close()
    assert "CONNECTED" not in res.stdout
    assert "DENIED" in res.stdout


@darwin_only
def test_os_sandbox_denies_write_outside_workspace_without_python_hooks(tmp_path: Path):
    outside = tmp_path / "escape.txt"
    res = _run_sandboxed_raw(tmp_path, (
        f"try:\n    open(r'{outside}','w').write('x')\n    print('WROTE')\n"
        "except OSError as e:\n    print('DENIED', e)\n"
    ))
    assert "WROTE" not in res.stdout and not outside.exists()
    assert "DENIED" in res.stdout


@darwin_only
def test_os_sandbox_denies_reading_user_home_without_python_hooks(tmp_path: Path):
    secret = Path.home() / ".aksa_cycle5_probe.txt"
    secret.write_text("TOP-SECRET", encoding="utf-8")
    try:
        res = _run_sandboxed_raw(tmp_path, (
            f"try:\n    print(open(r'{secret}').read())\nexcept OSError as e:\n    print('DENIED', e)\n"
        ))
    finally:
        secret.unlink(missing_ok=True)
    assert "TOP-SECRET" not in res.stdout
    assert "DENIED" in res.stdout


@darwin_only
def test_os_sandbox_denies_fork_without_python_hooks(tmp_path: Path):
    res = _run_sandboxed_raw(tmp_path, (
        "import os\ntry:\n    pid=os.fork()\n    print('FORKED')\n"
        "except OSError as e:\n    print('DENIED', e)\n"
    ))
    assert "FORKED" not in res.stdout
    assert "DENIED" in res.stdout


def test_os_sandbox_fails_closed_on_unsupported_platform(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sys, "platform", "freebsd")
    with pytest.raises(SandboxUnavailableError):
        wrap_command(["python"], tmp_path, [])


# ---- SEC-004-R4: real engine handshake (port 0 + nonce HMAC) ----------------------------------

def test_engine_owns_port_and_answers_nonce_hmac(tmp_path: Path):
    import queue
    import threading

    token = "aksa-cycle5-integration-token"
    env = {**os.environ, "AKSA_AUTH_TOKEN": token, "AKSA_APPDATA_DIR": str(tmp_path), "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "app.main", "--host", "127.0.0.1", "--port", "0", "--production"],
        cwd=ENGINE_ROOT,
        env=env,
        stderr=subprocess.PIPE,
        text=True,
    )
    q: queue.Queue[str | None] = queue.Queue()
    captured: list[str] = []

    def _reader() -> None:
        assert proc.stderr is not None
        for ln in proc.stderr:
            q.put(ln)
        q.put(None)

    threading.Thread(target=_reader, daemon=True).start()
    try:
        port = pid = None
        deadline = time.time() + 40
        while time.time() < deadline:
            remaining = max(0.05, deadline - time.time())
            try:
                line = q.get(timeout=min(0.25, remaining))
            except queue.Empty:
                if proc.poll() is not None:
                    break
                continue
            if line is None:
                break
            captured.append(line)
            m = re.search(r"\[AKSA_ENGINE_READY:port=(\d+):pid=(\d+)(?::launch_id=[^\]]*)?\]", line)
            if m:
                port, pid = int(m.group(1)), int(m.group(2))
                break
        assert port and port != 0, f"engine did not report a bound port; stderr={''.join(captured)}"
        assert pid == proc.pid
        nonce = "cycle5nonce"
        body = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/health?nonce={nonce}", timeout=10).read())
        expected = hmac.new(token.encode(), nonce.encode(), hashlib.sha256).hexdigest()
        assert body["engine"] == "aksa-engine"
        assert hmac.compare_digest(body["nonce_hmac"], expected)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


# ---- SKILL-002-R4 -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_bound_skill_requires_agent_id(tmp_path: Path):
    await db_manager.initialize()
    await db_manager.upsert_installed_skill({
        "skill_id": "bound-skill-r4", "display_name": "Bound", "enabled": True, "target_agent_id": "agent_x",
    })
    ws = tmp_path / "ws"
    ws.mkdir()
    with pytest.raises(PermissionError) as exc:
        await agent_skills_manager.execute_skill_script("bound-skill-r4", "scripts/run.py", str(ws), agent_id=None)
    assert "wajib disertakan" in str(exc.value)


# ---- SEC-002-R4 -------------------------------------------------------------------------------

def _enroll(store: PublisherTrustStore, root_priv, pid: str = "pub"):
    priv = ed25519.Ed25519PrivateKey.generate()
    b64 = base64.b64encode(priv.public_key().public_bytes_raw()).decode()
    sig = PublisherTrustStore.sign_publisher_delegation(pid, b64, root_priv)
    store.register_publisher(pid, b64, root_signature_b64=sig)


def _store(tmp_path: Path):
    root = ed25519.Ed25519PrivateKey.generate()
    root_b64 = base64.b64encode(root.public_key().public_bytes_raw()).decode()
    return root, root_b64, PublisherTrustStore(root_public_key_b64=root_b64, persist_path=tmp_path / "trust" / "t.json")


def test_trust_store_persist_failure_fails_closed_and_rolls_back(tmp_path: Path):
    root, _, store = _store(tmp_path)
    (tmp_path / "trust").mkdir()
    (tmp_path / "trust").chmod(0o500)  # read-only dir -> write fails
    try:
        with pytest.raises(Exception):
            _enroll(store, root)
    finally:
        (tmp_path / "trust").chmod(0o700)
    assert "pub" not in store._trusted_keys
    assert store._enrollment_audit_trail == []


def test_trust_store_file_is_0600_and_checksummed(tmp_path: Path):
    root, _, store = _store(tmp_path)
    _enroll(store, root)
    f = tmp_path / "trust" / "t.json"
    assert (f.stat().st_mode & 0o777) == 0o600
    assert "integrity_sha256" in json.loads(f.read_text())


def test_trust_store_tampered_or_corrupt_file_fails_closed(tmp_path: Path):
    root, root_b64, store = _store(tmp_path)
    _enroll(store, root)
    f = tmp_path / "trust" / "t.json"
    data = json.loads(f.read_text())
    data["publishers"]["evil"] = data["publishers"]["pub"]  # tamper without fixing checksum
    f.write_text(json.dumps(data))
    reloaded = PublisherTrustStore(root_public_key_b64=root_b64, persist_path=f)
    assert "pub" not in reloaded._trusted_keys and "evil" not in reloaded._trusted_keys
    with pytest.raises(PermissionError):
        _enroll(reloaded, root, "another")
    f.write_text("{not json")
    corrupt = PublisherTrustStore(root_public_key_b64=root_b64, persist_path=f)
    assert "pub" not in corrupt._trusted_keys


# ---- SEC-001-R4 -------------------------------------------------------------------------------

def test_mcp_self_declared_system_trusted_is_rejected():
    spoof = MCPServerConfig(id="evil_server", name="Evil", command="node", trust_level="system_trusted", permissions=["*"])
    allowed, reason = check_mcp_server_permissions(spoof, "write_file")
    assert allowed is False and "wildcard" in str(reason).lower()


# ---- AKSA-CYCLE-5: Symlink Traversal & Semantic Postconditions & Replay Evaluation ------------

@darwin_only
def test_os_sandbox_blocks_symlink_escape_attempt(tmp_path: Path):
    """Adversarial test: creating a symlink inside workspace pointing to user files is blocked by OS and sandbox."""
    secret = Path.home() / ".aksa_test_symlink_secret.txt"
    secret.write_text("SENSITIVE_USER_DATA", encoding="utf-8")
    ws = tmp_path / "ws"
    ws.mkdir(exist_ok=True)
    symlink_path = ws / "symlink_to_user_secret.txt"

    try:
        res = _run_sandboxed_raw(tmp_path, f"""
import os
import sys

target = r'{secret}'
sym = r'{symlink_path}'
try:
    if hasattr(os, "symlink"):
        os.symlink(target, sym)
    # Attempt reading user secret through symlink
    with open(sym, 'r') as f:
        print("LEAKED:", f.read())
except (OSError, PermissionError) as exc:
    print("BLOCKED_SYMLINK_READ:", exc)
""")
        assert "LEAKED" not in res.stdout
        assert "BLOCKED" in res.stdout or "DENIED" in res.stdout
    finally:
        secret.unlink(missing_ok=True)


def test_sandbox_runner_blocks_symlink_pointing_outside_workspace(tmp_path: Path):
    """Adversarial test: sandbox_runner.py blocks symlink creation and reading pointing outside workspace."""
    outside = tmp_path / "outside_target.txt"
    outside.write_text("OUTSIDE_PAYLOAD", encoding="utf-8")
    ws = tmp_path / "ws"
    ws.mkdir(exist_ok=True)
    script = ws / "symlink_test.py"
    script.write_text(f"""
import os
import sys

target = r'{outside}'
sym = r'{ws / "symlink.txt"}'
try:
    os.symlink(target, sym)
    with open(sym, 'r') as f:
        print("LEAKED:", f.read())
except PermissionError as exc:
    sys.stderr.write(f"BLOCKED: {{exc}}\\n")
    sys.exit(13)
""", encoding="utf-8")

    res = subprocess.run(
        [sys.executable, "-m", "app.skills.sandbox_runner", "--script", str(script), "--workspace", str(ws)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert res.returncode == 13
    assert "di luar batas aman" in res.stderr or "di luar folder kerja dilarang" in res.stderr
    assert "LEAKED" not in res.stdout


def test_artifact_postcondition_breakdown_detects_empty_semantic_shells(tmp_path: Path):
    """Verify granular gates: file_created, format_valid, semantic_postcondition_passed."""
    from app.core.orchestrator import get_artifact_postcondition_breakdown, verify_artifact_postcondition
    import docx
    import openpyxl

    # 1. Excel file with empty sheet (no rows/data)
    empty_xlsx = tmp_path / "empty_sheet.xlsx"
    wb = openpyxl.Workbook()
    wb.save(str(empty_xlsx))
    wb.close()

    bd_empty_xlsx = get_artifact_postcondition_breakdown(empty_xlsx)
    assert bd_empty_xlsx["file_created"] is True
    assert bd_empty_xlsx["format_valid"] is True
    assert bd_empty_xlsx["semantic_postcondition_passed"] is False  # empty cells!
    ok_empty, _ = verify_artifact_postcondition(empty_xlsx)
    assert ok_empty is False

    # 2. Populated Excel file
    valid_xlsx = tmp_path / "populated.xlsx"
    wb2 = openpyxl.Workbook()
    ws = wb2.active
    ws["A1"] = "Pendapatan Bulanan"
    ws["B1"] = 15000000
    wb2.save(str(valid_xlsx))
    wb2.close()

    bd_valid_xlsx = get_artifact_postcondition_breakdown(valid_xlsx)
    assert bd_valid_xlsx["file_created"] is True
    assert bd_valid_xlsx["format_valid"] is True
    assert bd_valid_xlsx["semantic_postcondition_passed"] is True
    ok_valid, _ = verify_artifact_postcondition(valid_xlsx)
    assert ok_valid is True

    # 3. Empty DOCX (0 paragraphs)
    empty_docx = tmp_path / "empty.docx"
    doc = docx.Document()
    doc.save(str(empty_docx))

    bd_empty_docx = get_artifact_postcondition_breakdown(empty_docx)
    assert bd_empty_docx["file_created"] is True
    assert bd_empty_docx["format_valid"] is True
    assert bd_empty_docx["semantic_postcondition_passed"] is False


def test_candidate_skill_replay_and_evaluation_simulation():
    """Verify replay simulation evaluates procedural DAG and catches dangerous parameter injections."""
    from app.core.agent_learning import SkillEvaluator

    valid_md = """---
name: Laporan Rekap Bulanan
description: Otomasi kalkulasi laporan bulanan
metadata:
  owner-agent: "agent_analyst"
  source: "learned"
---
# Alur Prosedural
1. Muat data
2. Kalkulasi
"""

    # 1. Clean candidate data with valid traces
    clean_candidate = {
        "structured_traces": [
            {
                "tool_name": "read_financial_data",
                "input_summary": {"path": "data.csv"},
                "output_summary": {"rows": 50},
                "status": "success",
            },
            {
                "tool_name": "calculate_excel_summary",
                "input_summary": {"source": "data.csv", "dest": "report.xlsx"},
                "output_summary": {"status": "created"},
                "status": "success",
            },
        ],
    }

    eval_clean = SkillEvaluator.evaluate(valid_md, "clean_cand_01", candidate_data=clean_candidate)
    assert eval_clean.passed is True
    assert eval_clean.replay_passed is True
    assert len(eval_clean.replay_trace) == 2

    # 2. Malicious candidate injecting command execution in parameters
    malicious_candidate = {
        "structured_traces": [
            {
                "tool_name": "read_financial_data",
                "input_summary": {"cmd": "rm -rf /"},
                "output_summary": "",
                "status": "success",
            },
        ],
    }

    eval_malicious = SkillEvaluator.evaluate(valid_md, "evil_cand_01", candidate_data=malicious_candidate)
    assert eval_malicious.passed is False
    assert eval_malicious.replay_passed is False

