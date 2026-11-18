"""Regression tests for P1-01: Credential Vault Hardening, DPAPI, corruption, and fail-closed."""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch
import pytest

from app.config import settings
from app.core.credential_vault import (
    CredentialVault,
    KeyringUnavailableError,
)


def test_vault_ciphertext_corruption_fails_safely_without_leak(tmp_path: Path) -> None:
    """Verify that corrupted ciphertext or nonce returns None safely without raising or leaking (P1-01)."""
    vault = CredentialVault(vault_dir=tmp_path)
    vault._force_keyring_failure = True
    secret = "sk-ant-api03-test-secret-corruption-payload"

    meta = vault.store_secret("anthropic", secret)
    cred_ref = meta["credential_ref"]

    # Clear in-memory cache to force reading from disk
    vault._memory_cache.clear()

    # Corrupt the ciphertext payload on disk
    vault_file = vault.fallback_vault_file
    data = json.loads(vault_file.read_text(encoding="utf-8"))
    orig_ct = base64.b64decode(data[cred_ref]["ciphertext"])
    corrupted_ct = bytearray(orig_ct)
    corrupted_ct[0] ^= 0xFF  # Flip bits
    data[cred_ref]["ciphertext"] = base64.b64encode(corrupted_ct).decode("ascii")
    vault_file.write_text(json.dumps(data), encoding="utf-8")

    # Retrieval of corrupted payload must return None (fail closed safely)
    result = vault.retrieve_secret(cred_ref)
    assert result is None


def test_vault_strict_os_filesystem_permissions(tmp_path: Path) -> None:
    """Verify file and directory permissions (0o600 file, 0o700 dir) on POSIX (P1-01)."""
    if sys.platform == "win32":
        pytest.skip("POSIX permissions test not applicable to Windows")

    vault_dir = tmp_path / "secure_vault"
    vault = CredentialVault(vault_dir=vault_dir)
    vault._force_keyring_failure = True
    vault.store_secret("gemini", "AIzaSyTestSecret12345")

    # Directory permissions
    dir_stat = vault_dir.stat()
    assert (dir_stat.st_mode & 0o777) == 0o700

    # Fallback vault file permissions
    vault_file = vault.fallback_vault_file
    assert vault_file.exists()
    assert (vault_file.stat().st_mode & 0o777) == 0o600

    # Key file permissions
    key_file = vault.os_key_file
    assert key_file.exists()
    assert (key_file.stat().st_mode & 0o777) == 0o600


def test_production_fails_closed_when_keyring_unavailable_without_opt_in(tmp_path: Path) -> None:
    """Verify that in production mode, unencrypted fallback key is rejected (P1-01)."""
    orig_dev = settings.dev_mode
    orig_test = settings.testing
    try:
        settings.dev_mode = False
        settings.testing = False

        # In production without vault_dir override or opt-in env
        with patch.dict(os.environ, {}, clear=True):
            vault = CredentialVault(vault_dir=None)
            vault._force_keyring_failure = True

            with pytest.raises(KeyringUnavailableError) as exc_info:
                vault.store_secret("openai", "sk-prod-test-secret-fail-closed")

            assert "fail-closed" in str(exc_info.value)
            assert "sk-prod-test-secret-fail-closed" not in str(exc_info.value)
    finally:
        settings.dev_mode = orig_dev
        settings.testing = orig_test


def test_dpapi_mock_lifecycle_on_windows(tmp_path: Path, monkeypatch) -> None:
    """Verify Windows DPAPI key encryption and recovery simulation (P1-01)."""
    monkeypatch.setattr(sys, "platform", "win32")

    mock_dpapi_store = {}

    def mock_protect(data: bytes) -> bytes:
        token = b"DPAPI_PROTECTED_" + data
        mock_dpapi_store[token] = data
        return token

    def mock_unprotect(data: bytes) -> bytes | None:
        return mock_dpapi_store.get(data)

    with patch("app.core.credential_vault._dpapi_protect", side_effect=mock_protect), \
         patch("app.core.credential_vault._dpapi_unprotect", side_effect=mock_unprotect):

        vault = CredentialVault(vault_dir=tmp_path)
        vault._force_keyring_failure = True
        secret = "sk-windows-dpapi-secret-999"

        meta = vault.store_secret("groq", secret)
        assert meta["backend"] == "os_secure_file_vault"

        # Assert DPAPI key file was written with DPAPI protection
        assert vault.dpapi_key_file.exists()
        dpapi_content = vault.dpapi_key_file.read_bytes()
        assert dpapi_content.startswith(b"DPAPI_PROTECTED_")

        # Memory cache clear and retrieve
        vault._memory_cache.clear()
        retrieved = vault.retrieve_secret(meta["credential_ref"])
        assert retrieved == secret

