"""Regression tests for P0-5: Keyring OS store, AES-GCM fallback, and zero argv/plaintext leaks."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from unittest.mock import patch
import pytest

from app.core.credential_vault import CredentialVault, mask_secret


def test_p0_vault_store_retrieve_and_delete(tmp_path: Path) -> None:
    vault = CredentialVault(vault_dir=tmp_path)
    secret = "sk-ant-api03-very-secret-test-key-1234567890"

    # 1. Store secret
    meta = vault.store_secret("anthropic", secret)
    cred_ref = meta["credential_ref"]

    assert meta["provider"] == "anthropic"
    assert meta["masked_preview"] == mask_secret(secret)
    assert secret not in meta["masked_preview"]
    assert meta["backend"] in ("os_keyring", "aes_gcm_fallback")

    # 2. Retrieve secret
    retrieved = vault.retrieve_secret(cred_ref)
    assert retrieved == secret

    # 3. Assert NO plaintext master key file exists
    assert not (tmp_path / ".vault_master_key").exists()

    # 4. Assert NO plaintext secret exists in any file under tmp_path
    for p in tmp_path.rglob("*"):
        if p.is_file():
            content = p.read_bytes()
            assert secret.encode("utf-8") not in content, f"Plaintext secret found in {p.name}"

    # 5. Delete secret
    deleted = vault.delete_secret(cred_ref)
    assert deleted is True
    assert vault.retrieve_secret(cred_ref) is None


def test_p0_legacy_vault_migration_and_shred(tmp_path: Path) -> None:
    """Verify that legacy HMAC-CTR vault files and .vault_master_key are securely migrated and deleted."""
    legacy_key = os.urandom(32)
    (tmp_path / ".vault_master_key").write_bytes(legacy_key)

    # Construct a legacy sealed entry
    import hmac
    import hashlib
    raw_secret = b"AIzaSyLegacyKeyToMigrate99999"
    nonce = os.urandom(16)
    keystream = bytearray()
    counter = 0
    while len(keystream) < len(raw_secret):
        block = hmac.new(legacy_key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        keystream.extend(block)
        counter += 1
    xored = bytes(a ^ b for a, b in zip(raw_secret, keystream[: len(raw_secret)]))
    legacy_entry = {
        "cred_gemini_legacy": {
            "backend": "sealed_local_vault",
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(xored).decode("ascii"),
            "tag": base64.b64encode(hmac.new(legacy_key, nonce + xored, hashlib.sha256).digest()).decode("ascii"),
        }
    }
    (tmp_path / "credentials.vault").write_text(json.dumps(legacy_entry), encoding="utf-8")

    # Initialize new vault pointing to this dir
    vault = CredentialVault(vault_dir=tmp_path)
    retrieved = vault.retrieve_secret("cred_gemini_legacy")

    # Secret must be recovered correctly
    assert retrieved == "AIzaSyLegacyKeyToMigrate99999"

    # Legacy files must be shredded (deleted)
    assert not (tmp_path / "credentials.vault").exists()
    assert not (tmp_path / ".vault_master_key").exists()


def test_p0_no_subprocess_calls_during_vault_operations(tmp_path: Path) -> None:
    """Verify that storing, retrieving, and deleting secrets never executes CLI subprocesses (no ps leaks)."""
    vault = CredentialVault(vault_dir=tmp_path)
    secret = "gsk_no_subprocess_leak_test_9876543210"

    with patch("subprocess.run") as mock_run, patch("subprocess.Popen") as mock_popen:
        meta = vault.store_secret("groq", secret)
        retrieved = vault.retrieve_secret(meta["credential_ref"])
        vault.delete_secret(meta["credential_ref"])

        assert mock_run.call_count == 0, "subprocess.run was unexpectedly called"
        assert mock_popen.call_count == 0, "subprocess.Popen was unexpectedly called"
        assert retrieved == secret
