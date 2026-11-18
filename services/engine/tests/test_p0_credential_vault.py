"""Regression tests for P0-5 & P1.1: Keyring OS store, fail-closed enforcement, and zero plaintext leaks."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from unittest.mock import patch
import pytest

from app.core.credential_vault import (
    CredentialVault,
    KeyringUnavailableError,
    _derive_legacy_metadata_key,
    mask_secret,
)


def test_p0_vault_store_retrieve_and_delete(tmp_path: Path) -> None:
    vault = CredentialVault(vault_dir=tmp_path)
    secret = "sk-ant-api03-very-secret-test-key-1234567890"

    # 1. Store secret
    meta = vault.store_secret("anthropic", secret)
    cred_ref = meta["credential_ref"]

    assert meta["provider"] == "anthropic"
    assert meta["masked_preview"] == mask_secret(secret)
    assert secret not in meta["masked_preview"]
    assert meta["backend"] in ("os_keyring", "os_secure_file_vault")

    # 2. Retrieve secret
    retrieved = vault.retrieve_secret(cred_ref)
    assert retrieved == secret

    # 3. Assert NO plaintext master key file exists
    assert not (tmp_path / ".vault_master_key").exists()

    # 4. Assert NO plaintext secret exists in any file under tmp_path
    for p in tmp_path.rglob("*"):
        if p.is_file() and p.name != ".vault_key_v2":
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


def test_p1_keyring_unavailable_fails_closed_without_metadata_fallback(tmp_path: Path) -> None:
    """Verify that if the OS keyring and secure OS storage fail, vault fails closed instead of using weak metadata."""
    vault = CredentialVault(vault_dir=tmp_path)
    vault._force_keyring_failure = True
    vault._allow_os_key_fallback = False
    secret = "sk-super-secret-key-fail-closed"

    # Must raise KeyringUnavailableError
    with pytest.raises(KeyringUnavailableError) as exc_info:
        vault.store_secret("openai", secret)

    assert "tidak tersedia" in str(exc_info.value)
    # Ensure raw secret is not in exception text
    assert secret not in str(exc_info.value)


def test_p1_explicit_master_key_fallback_works_when_configured(tmp_path: Path) -> None:
    """Verify that an explicit CSPRNG master key (e.g. CI/container) allows secure storage when keyring fails."""
    master_key = os.urandom(32)
    vault = CredentialVault(vault_dir=tmp_path, master_key=master_key)
    vault._force_keyring_failure = True
    secret = "sk-explicit-key-success-12345"

    meta = vault.store_secret("deepseek", secret)
    assert meta["backend"] in ("os_keyring", "os_secure_file_vault")

    # Clear memory cache and retrieve using the explicit master key
    vault._memory_cache.clear()
    retrieved = vault.retrieve_secret(meta["credential_ref"])
    assert retrieved == secret

    # Wrong master key cannot decrypt
    wrong_vault = CredentialVault(vault_dir=tmp_path, master_key=os.urandom(32))
    wrong_vault._force_keyring_failure = True
    assert wrong_vault.retrieve_secret(meta["credential_ref"]) is None


def test_p1_legacy_metadata_vault_migrated_and_shredded(tmp_path: Path) -> None:
    """Verify that older metadata-derived fallback entries are safely migrated and readable."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    legacy_key = _derive_legacy_metadata_key()
    aesgcm = AESGCM(legacy_key)
    nonce = os.urandom(12)
    secret_text = "AIzaSyMetadataEncryptedOldSecret99"
    ct = aesgcm.encrypt(nonce, secret_text.encode("utf-8"), None)

    old_entries = {
        "cred_legacy_meta_1": {
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ct).decode("ascii"),
        }
    }
    fallback_file = tmp_path / "credentials.aesgcm.vault"
    fallback_file.write_text(json.dumps(old_entries), encoding="utf-8")

    # Launch new vault (which has working OS keyring or CSPRNG vault)
    vault = CredentialVault(vault_dir=tmp_path)
    retrieved = vault.retrieve_secret("cred_legacy_meta_1")

    assert retrieved == secret_text


def test_p1_secret_rotation_preserves_ref_and_updates_timestamp(tmp_path: Path) -> None:
    """Verify that rotating a secret updates the stored value and timestamp under the same credential_ref."""
    vault = CredentialVault(vault_dir=tmp_path)
    old_secret = "sk-key-v1-old-12345678"
    new_secret = "sk-key-v2-new-87654321"

    meta1 = vault.store_secret("gemini", old_secret)
    cred_ref = meta1["credential_ref"]
    assert vault.retrieve_secret(cred_ref) == old_secret

    # Rotate secret using existing_ref
    meta2 = vault.store_secret("gemini", new_secret, existing_ref=cred_ref)
    assert meta2["credential_ref"] == cred_ref
    vault._memory_cache.clear()
    assert vault.retrieve_secret(cred_ref) == new_secret
