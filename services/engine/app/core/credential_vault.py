"""OS Credential Vault Bridge (Windows DPAPI / macOS Keychain / Encrypted Local Vault).

Ensures API keys and tokens are NEVER stored in plaintext in SQLite.
SQLite only stores `credential_ref` and non-sensitive metadata.
"""

from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes
import hashlib
import hmac
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings


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


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _win32_dpapi_encrypt(plaintext: bytes) -> bytes | None:
    """Encrypt bytes using Windows native CryptProtectData (Current User scope)."""
    if sys.platform != "win32":
        return None
    try:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        buf = ctypes.create_string_buffer(plaintext, len(plaintext))
        blob_in = _DataBlob(len(plaintext), buf)
        blob_out = _DataBlob()
        CRYPTPROTECT_UI_FORBIDDEN = 0x01
        if crypt32.CryptProtectData(
            ctypes.byref(blob_in),
            "AKSA_CREDENTIAL_VAULT",
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(blob_out),
        ):
            encrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            kernel32.LocalFree(blob_out.pbData)
            return encrypted
    except Exception:
        pass
    return None


def _win32_dpapi_decrypt(ciphertext: bytes) -> bytes | None:
    """Decrypt bytes using Windows native CryptUnprotectData."""
    if sys.platform != "win32":
        return None
    try:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        buf = ctypes.create_string_buffer(ciphertext, len(ciphertext))
        blob_in = _DataBlob(len(ciphertext), buf)
        blob_out = _DataBlob()
        CRYPTPROTECT_UI_FORBIDDEN = 0x01
        if crypt32.CryptUnprotectData(
            ctypes.byref(blob_in),
            None,
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(blob_out),
        ):
            decrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            kernel32.LocalFree(blob_out.pbData)
            return decrypted
    except Exception:
        pass
    return None


class CredentialVault:
    """Cross-platform OS Credential Vault storing secrets outside SQLite."""

    def __init__(self, vault_dir: Path | None = None) -> None:
        self._vault_dir = vault_dir
        self._memory_cache: dict[str, str] = {}

    @property
    def vault_file(self) -> Path:
        base = self._vault_dir or settings.data_dir
        base.mkdir(parents=True, exist_ok=True)
        return base / "credentials.vault"

    @property
    def key_file(self) -> Path:
        base = self._vault_dir or settings.data_dir
        base.mkdir(parents=True, exist_ok=True)
        return base / ".vault_master_key"

    def _get_or_create_master_key(self) -> bytes:
        if self.key_file.exists():
            raw = self.key_file.read_bytes()
            if len(raw) >= 32:
                return raw[:32]
        key = os.urandom(32)
        self.key_file.write_bytes(key)
        try:
            os.chmod(self.key_file, 0o600)
        except Exception:
            pass
        return key

    def _seal_secret(self, plaintext: str) -> dict[str, str]:
        raw_bytes = plaintext.encode("utf-8")
        # 1. Try Windows native DPAPI first
        dpapi_blob = _win32_dpapi_encrypt(raw_bytes)
        if dpapi_blob is not None:
            return {
                "backend": "windows_dpapi",
                "ciphertext": base64.b64encode(dpapi_blob).decode("ascii"),
            }

        # 2. Fallback authenticated encryption (HMAC-SHA256 CTR stream)
        master_key = self._get_or_create_master_key()
        nonce = os.urandom(16)
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(raw_bytes):
            block = hmac.new(
                master_key,
                nonce + counter.to_bytes(4, "big"),
                hashlib.sha256,
            ).digest()
            keystream.extend(block)
            counter += 1
        xored = bytes(a ^ b for a, b in zip(raw_bytes, keystream[: len(raw_bytes)]))
        tag = hmac.new(master_key, nonce + xored, hashlib.sha256).digest()
        return {
            "backend": "sealed_local_vault",
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(xored).decode("ascii"),
            "tag": base64.b64encode(tag).decode("ascii"),
        }

    def _unseal_secret(self, entry: dict[str, str]) -> str | None:
        backend = entry.get("backend")
        if backend == "windows_dpapi":
            raw_cipher = base64.b64decode(entry["ciphertext"])
            plain = _win32_dpapi_decrypt(raw_cipher)
            return plain.decode("utf-8") if plain is not None else None

        if backend == "sealed_local_vault":
            master_key = self._get_or_create_master_key()
            nonce = base64.b64decode(entry["nonce"])
            xored = base64.b64decode(entry["ciphertext"])
            tag = base64.b64decode(entry["tag"])
            expected_tag = hmac.new(master_key, nonce + xored, hashlib.sha256).digest()
            if not hmac.compare_digest(tag, expected_tag):
                return None
            keystream = bytearray()
            counter = 0
            while len(keystream) < len(xored):
                block = hmac.new(
                    master_key,
                    nonce + counter.to_bytes(4, "big"),
                    hashlib.sha256,
                ).digest()
                keystream.extend(block)
                counter += 1
            raw_bytes = bytes(a ^ b for a, b in zip(xored, keystream[: len(xored)]))
            return raw_bytes.decode("utf-8")
        return None

    def _load_vault_entries(self) -> dict[str, dict[str, str]]:
        if not self.vault_file.exists():
            return {}
        try:
            return json.loads(self.vault_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_vault_entries(self, entries: dict[str, dict[str, str]]) -> None:
        self.vault_file.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        try:
            os.chmod(self.vault_file, 0o600)
        except Exception:
            pass

    def store_secret(self, provider: str, secret: str, existing_ref: str | None = None) -> dict[str, str]:
        """Store a secret in the OS vault and return its opaque credential_ref and masked preview."""
        cleaned = secret.strip()
        if not cleaned:
            raise ValueError("Secret tidak boleh kosong.")

        cred_ref = existing_ref or f"cred_{provider}_{uuid.uuid4().hex[:10]}"

        # On macOS, attempt Keychain storage first
        if sys.platform == "darwin":
            try:
                subprocess.run(
                    [
                        "security",
                        "add-generic-password",
                        "-U",
                        "-s",
                        "com.aksa.desktop.vault",
                        "-a",
                        cred_ref,
                        "-w",
                        cleaned,
                    ],
                    check=False,
                    capture_output=True,
                    timeout=3.0,
                )
            except Exception:
                pass

        entries = self._load_vault_entries()
        entries[cred_ref] = self._seal_secret(cleaned)
        self._save_vault_entries(entries)
        self._memory_cache[cred_ref] = cleaned

        return {
            "credential_ref": cred_ref,
            "provider": provider,
            "masked_preview": mask_secret(cleaned),
            "backend": entries[cred_ref]["backend"],
            "updated_at": _now_iso(),
        }

    def retrieve_secret(self, credential_ref: str) -> str | None:
        """Retrieve a decrypted secret by its credential_ref."""
        if not credential_ref:
            return None
        if credential_ref in self._memory_cache:
            return self._memory_cache[credential_ref]

        entries = self._load_vault_entries()
        entry = entries.get(credential_ref)
        if entry:
            unsealed = self._unseal_secret(entry)
            if unsealed is not None:
                self._memory_cache[credential_ref] = unsealed
                return unsealed

        if sys.platform == "darwin":
            try:
                proc = subprocess.run(
                    [
                        "security",
                        "find-generic-password",
                        "-s",
                        "com.aksa.desktop.vault",
                        "-a",
                        credential_ref,
                        "-w",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=3.0,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    val = proc.stdout.strip()
                    self._memory_cache[credential_ref] = val
                    return val
            except Exception:
                pass

        return None

    def delete_secret(self, credential_ref: str) -> bool:
        """Remove a secret from the OS vault."""
        self._memory_cache.pop(credential_ref, None)
        entries = self._load_vault_entries()
        existed = entries.pop(credential_ref, None) is not None
        self._save_vault_entries(entries)

        if sys.platform == "darwin":
            try:
                subprocess.run(
                    [
                        "security",
                        "delete-generic-password",
                        "-s",
                        "com.aksa.desktop.vault",
                        "-a",
                        credential_ref,
                    ],
                    check=False,
                    capture_output=True,
                    timeout=3.0,
                )
            except Exception:
                pass

        return existed


credential_vault = CredentialVault()
