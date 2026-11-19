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
    monkeypatch.setattr(sys, "platform", "win32")
    with pytest.raises(SandboxUnavailableError):
        wrap_command(["python"], tmp_path, [])


# ---- SEC-004-R4: real engine handshake (port 0 + nonce HMAC) ----------------------------------

def test_engine_owns_port_and_answers_nonce_hmac(tmp_path: Path):
    token = "aksa-cycle5-integration-token"
    env = {**os.environ, "AKSA_AUTH_TOKEN": token, "AKSA_APPDATA_DIR": str(tmp_path), "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "app.main", "--host", "127.0.0.1", "--port", "0", "--production"],
        cwd=ENGINE_ROOT, env=env, stderr=subprocess.PIPE, text=True,
    )
    try:
        port = pid = None
        deadline = time.time() + 40
        while time.time() < deadline:
            line = proc.stderr.readline()
            m = re.search(r"\[AKSA_ENGINE_READY:port=(\d+):pid=(\d+)\]", line or "")
            if m:
                port, pid = int(m.group(1)), int(m.group(2))
                break
            if proc.poll() is not None:
                break
        assert port and port != 0, "engine did not report a bound port"
        assert pid == proc.pid
        nonce = "cycle5nonce"
        body = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/health?nonce={nonce}", timeout=10).read())
        expected = hmac.new(token.encode(), nonce.encode(), hashlib.sha256).hexdigest()
        assert body["engine"] == "aksa-engine"
        assert hmac.compare_digest(body["nonce_hmac"], expected)
    finally:
        proc.terminate()
        proc.wait(timeout=10)


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
