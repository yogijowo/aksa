"""OS Credential Vault Bridge (OS Keychain / Windows Credential Manager / AES-GCM Encrypted Fallback).

Ensures API keys and tokens are NEVER stored in plaintext in SQLite or on disk.
SQLite only stores `credential_ref` and non-sensitive masked metadata.
Eliminates subprocess CLI argv leaking and insecure home-made encryption (P0-5).
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import json
import os
import platform
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import keyring
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from app.config import settings

SERVICE_NAME = "com.aksa.desktop.vault"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def mask_secret(secret: str) -> str:
    """Return a safe display mask for a secret without exposing its value."""
    cleaned = secret.strip()
    if not cleaned:
        return ""
    if len(cleaned) > 8:
        return f"{cleaned[:4]}••••••••{cleaned[-4:]}"
    return "••••••••"


def _derive_fallback_key() -> bytes:
    """Derive a 256-bit AES-GCM key from OS environment and machine characteristics."""
    entropy = (
        platform.node()
        + getpass.getuser()
        + str(Path.home())
        + sys.platform
    ).encode("utf-8")
    salt = hashlib.sha256(b"AKSA_SECURE_VAULT_SALT_v2" + sys.platform.encode("utf-8")).digest()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    return kdf.derive(entropy)


class CredentialVault:
    """Cross-platform OS Credential Vault storing secrets in the OS keyring."""

    def __init__(self, vault_dir: Path | None = None) -> None:
        self._vault_dir = vault_dir
        self._memory_cache: dict[str, str] = {}
        self._has_migrated_legacy = False

    @property
    def fallback_vault_file(self) -> Path:
        base = self._vault_dir or settings.data_dir
        base.mkdir(parents=True, exist_ok=True)
        return base / "credentials.aesgcm.vault"

    @property
    def legacy_vault_file(self) -> Path:
        base = self._vault_dir or settings.data_dir
        return base / "credentials.vault"

    @property
    def legacy_key_file(self) -> Path:
        base = self._vault_dir or settings.data_dir
        return base / ".vault_master_key"

    def _migrate_legacy_vault_if_needed(self) -> None:
        """Migrate older HMAC-CTR vault files into keyring and securely shred legacy files."""
        if self._has_migrated_legacy:
            return
        self._has_migrated_legacy = True

        if not self.legacy_vault_file.exists():
            return

        try:
            # Read legacy master key if present
            legacy_key: bytes | None = None
            if self.legacy_key_file.exists():
                raw_k = self.legacy_key_file.read_bytes()
                if len(raw_k) >= 32:
                    legacy_key = raw_k[:32]

            legacy_data: dict[str, Any] = json.loads(self.legacy_vault_file.read_text(encoding="utf-8"))
            for cred_ref, entry in legacy_data.items():
                if not isinstance(entry, dict):
                    continue
                backend = entry.get("backend")
                plain: str | None = None
                if backend == "sealed_local_vault" and legacy_key and "ciphertext" in entry and "nonce" in entry:
                    import hmac
                    nonce = base64.b64decode(entry["nonce"])
                    xored = base64.b64decode(entry["ciphertext"])
                    keystream = bytearray()
                    counter = 0
                    while len(keystream) < len(xored):
                        block = hmac.new(
                            legacy_key,
                            nonce + counter.to_bytes(4, "big"),
                            hashlib.sha256,
                        ).digest()
                        keystream.extend(block)
                        counter += 1
                    raw_bytes = bytes(a ^ b for a, b in zip(xored, keystream[: len(xored)]))
                    plain = raw_bytes.decode("utf-8")

                if plain:
                    self._store_in_keyring(cred_ref, plain)
                    self._memory_cache[cred_ref] = plain

            # Securely shred legacy files
            self._shred_file(self.legacy_vault_file)
            if self.legacy_key_file.exists():
                self._shred_file(self.legacy_key_file)
        except Exception:
            pass

    def _shred_file(self, target: Path) -> None:
        """Overwrite file with zeros before unlinking to prevent disk recovery."""
        try:
            size = target.stat().st_size
            target.write_bytes(b"\x00" * size)
            target.unlink()
        except Exception:
            try:
                target.unlink(missing_ok=True)
            except Exception:
                pass

    def _store_in_keyring(self, credential_ref: str, secret: str) -> bool:
        try:
            keyring.set_password(SERVICE_NAME, credential_ref, secret)
            return True
        except Exception:
            return False

    def _get_from_keyring(self, credential_ref: str) -> str | None:
        try:
            return keyring.get_password(SERVICE_NAME, credential_ref)
        except Exception:
            return None

    def _delete_from_keyring(self, credential_ref: str) -> bool:
        try:
            keyring.delete_password(SERVICE_NAME, credential_ref)
            return True
        except Exception:
            return False

    # --- AES-GCM Fallback Storage ---
    def _aesgcm_encrypt(self, plaintext: str) -> dict[str, str]:
        key = _derive_fallback_key()
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # Standard 96-bit nonce for AES-GCM
        ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return {
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ct).decode("ascii"),
        }

    def _aesgcm_decrypt(self, payload: dict[str, str]) -> str | None:
        try:
            key = _derive_fallback_key()
            aesgcm = AESGCM(key)
            nonce = base64.b64decode(payload["nonce"])
            ct = base64.b64decode(payload["ciphertext"])
            pt = aesgcm.decrypt(nonce, ct, None)
            return pt.decode("utf-8")
        except Exception:
            return None

    def _load_fallback_entries(self) -> dict[str, dict[str, str]]:
        if not self.fallback_vault_file.exists():
            return {}
        try:
            return json.loads(self.fallback_vault_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_fallback_entries(self, entries: dict[str, dict[str, str]]) -> None:
        self.fallback_vault_file.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        try:
            os.chmod(self.fallback_vault_file, 0o600)
        except Exception:
            pass

    def store_secret(self, provider: str, secret: str, existing_ref: str | None = None) -> dict[str, str]:
        """Store a secret in the OS vault and return opaque metadata without leaking secrets."""
        cleaned = secret.strip()
        if not cleaned:
            raise ValueError("Secret tidak boleh kosong.")

        self._migrate_legacy_vault_if_needed()
        cred_ref = existing_ref or f"cred_{provider}_{uuid.uuid4().hex[:10]}"

        # 1. Attempt OS Keyring storage first
        stored_in_os = self._store_in_keyring(cred_ref, cleaned)
        backend = "os_keyring" if stored_in_os else "aes_gcm_fallback"

        # 2. If OS Keyring failed (headless/container), use AES-GCM fallback
        if not stored_in_os:
            entries = self._load_fallback_entries()
            entries[cred_ref] = self._aesgcm_encrypt(cleaned)
            self._save_fallback_entries(entries)

        self._memory_cache[cred_ref] = cleaned

        return {
            "credential_ref": cred_ref,
            "provider": provider,
            "masked_preview": mask_secret(cleaned),
            "backend": backend,
            "updated_at": _now_iso(),
        }

    def retrieve_secret(self, credential_ref: str) -> str | None:
        """Retrieve a decrypted secret by its credential_ref."""
        if not credential_ref:
            return None
        if credential_ref in self._memory_cache:
            return self._memory_cache[credential_ref]

        self._migrate_legacy_vault_if_needed()

        # 1. Check OS Keyring
        val = self._get_from_keyring(credential_ref)
        if val is not None:
            self._memory_cache[credential_ref] = val
            return val

        # 2. Check AES-GCM Fallback
        entries = self._load_fallback_entries()
        entry = entries.get(credential_ref)
        if entry:
            decrypted = self._aesgcm_decrypt(entry)
            if decrypted is not None:
                self._memory_cache[credential_ref] = decrypted
                return decrypted

        return None

    def delete_secret(self, credential_ref: str) -> bool:
        """Remove a secret from the vault."""
        self._memory_cache.pop(credential_ref, None)
        deleted_from_keyring = self._delete_from_keyring(credential_ref)

        entries = self._load_fallback_entries()
        deleted_from_fallback = entries.pop(credential_ref, None) is not None
        if deleted_from_fallback:
            self._save_fallback_entries(entries)

        return deleted_from_keyring or deleted_from_fallback


credential_vault = CredentialVault()
