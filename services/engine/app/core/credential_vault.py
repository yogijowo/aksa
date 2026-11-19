"""OS Credential Vault Bridge (OS Keychain / Windows Credential Manager / Secure OS ACL Vault).

Ensures API keys and tokens are NEVER stored in plaintext in SQLite or on disk.
OS Keyring is the primary secure storage. No predictable machine metadata
(hostname, username, home directory) is ever used as an encryption key (P0-5, P1.1).
If the OS Keyring is unavailable or denied, a CSPRNG 256-bit random key protected
by OS filesystem user ACL permissions (0o600) is used as a secure OS-backed fallback.
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
import keyring.errors
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from app.config import settings

SERVICE_NAME = "com.aksa.desktop.vault"


class VaultError(Exception):
    """Base exception for credential vault operations."""
    pass


class KeyringUnavailableError(VaultError):
    """Raised when OS Keyring and secure OS key storage are both unavailable or denied."""
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dpapi_protect(data: bytes) -> bytes | None:
    """Encrypt data using Windows DPAPI (CryptProtectData)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        if isinstance(ctypes.WinDLL, type) and isinstance(kernel32, ctypes.WinDLL):
            kernel32.LocalFree.argtypes = [ctypes.c_void_p]
            kernel32.LocalFree.restype = ctypes.c_void_p

        raw_buf = ctypes.create_string_buffer(data)
        blob_in = DATA_BLOB(len(data), ctypes.cast(raw_buf, ctypes.POINTER(ctypes.c_byte)))
        blob_out = DATA_BLOB()

        # CRYPTPROTECT_UI_FORBIDDEN = 0x1
        if crypt32.CryptProtectData(ctypes.byref(blob_in), "AKSA_VAULT_KEY", None, None, None, 1, ctypes.byref(blob_out)):
            out_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            kernel32.LocalFree(blob_out.pbData)
            return out_bytes
        return None
    except Exception:
        return None


def _dpapi_unprotect(data: bytes) -> bytes | None:
    """Decrypt data using Windows DPAPI (CryptUnprotectData)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        if isinstance(ctypes.WinDLL, type) and isinstance(kernel32, ctypes.WinDLL):
            kernel32.LocalFree.argtypes = [ctypes.c_void_p]
            kernel32.LocalFree.restype = ctypes.c_void_p

        raw_buf = ctypes.create_string_buffer(data)
        blob_in = DATA_BLOB(len(data), ctypes.cast(raw_buf, ctypes.POINTER(ctypes.c_byte)))
        blob_out = DATA_BLOB()

        if crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 1, ctypes.byref(blob_out)):
            out_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            kernel32.LocalFree(blob_out.pbData)
            return out_bytes
        return None
    except Exception:
        return None


def mask_secret(secret: str) -> str:
    """Return a safe display mask for a secret without exposing its value."""
    cleaned = secret.strip()
    if not cleaned:
        return ""
    if len(cleaned) > 8:
        return f"{cleaned[:4]}••••••••{cleaned[-4:]}"
    return "••••••••"


def _derive_legacy_metadata_key() -> bytes:
    """Derive legacy metadata key SOLELY for one-time migration of pre-P1.1 vault entries."""
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
    """Cross-platform OS Credential Vault storing secrets in the OS keyring (fail-closed, P1.1)."""

    def __init__(self, vault_dir: Path | None = None, master_key: bytes | None = None) -> None:
        self._vault_dir = vault_dir
        self._master_key = master_key
        self._memory_cache: dict[str, str] = {}
        self._has_migrated_legacy = False
        self._force_keyring_failure = False  # For test simulation
        self._allow_os_key_fallback = True   # Can be toggled false in tests to verify fail-closed

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

    @property
    def os_key_file(self) -> Path:
        base = self._vault_dir or settings.data_dir
        return base / ".vault_key_v2"

    @property
    def dpapi_key_file(self) -> Path:
        base = self._vault_dir or settings.data_dir
        return base / ".vault_key_v2.dpapi"

    def _get_active_master_key(self) -> bytes | None:
        """Get explicitly configured CSPRNG master key (e.g. from env for headless/CI)."""
        if self._master_key:
            return self._master_key
        env_key = os.environ.get("AKSA_VAULT_MASTER_KEY")
        if env_key:
            return hashlib.sha256(env_key.encode("utf-8")).digest()
        return None

    def _get_or_create_os_vault_key(self) -> bytes:
        """Retrieve or initialize a 256-bit CSPRNG vault key protected by DPAPI (Windows) or strict OS permissions (0o600).
        NEVER uses machine metadata (P1.1).
        """
        explicit = self._get_active_master_key()
        if explicit:
            return explicit

        if not self._allow_os_key_fallback:
            raise KeyringUnavailableError(
                "OS Keyring (Keychain/Credential Manager) tidak tersedia dan fallback dinonaktifkan."
            )

        base = self._vault_dir or settings.data_dir
        base.mkdir(parents=True, exist_ok=True)
        if sys.platform != "win32":
            try:
                os.chmod(base, 0o700)
            except Exception:
                pass

        # 1. On Windows: prioritize DPAPI protection
        if sys.platform == "win32":
            if self.dpapi_key_file.exists():
                try:
                    decrypted = _dpapi_unprotect(self.dpapi_key_file.read_bytes())
                    if decrypted and len(decrypted) == 32:
                        return decrypted
                except Exception:
                    pass

            new_key = os.urandom(32)
            protected = _dpapi_protect(new_key)
            if protected:
                self.dpapi_key_file.write_bytes(protected)
                return new_key

        # 2. Production fail-closed check: refuse unencrypted key on disk unless in dev/testing or explicit opt-in
        is_dev_or_test = settings.dev_mode or settings.testing
        allow_insecure_fallback = is_dev_or_test or os.environ.get("AKSA_ALLOW_INSECURE_VAULT_FALLBACK") == "1"
        if not allow_insecure_fallback:
            raise KeyringUnavailableError(
                "Penyimpanan OS Keyring (Keychain/Secret Service/DPAPI) tidak tersedia. "
                "Pada mode produksi, penyimpanan kunci tidak terenkripsi pada disk ditolak secara fail-closed (P1-01). "
                "Harap aktifkan Keychain OS atau tentukan AKSA_VAULT_MASTER_KEY."
            )

        # 3. Check if existing unencrypted key exists (only permitted in dev/test or with explicit opt-in)
        key_path = self.os_key_file
        if key_path.exists():
            try:
                if sys.platform != "win32":
                    try:
                        os.chmod(key_path, 0o600)
                    except Exception:
                        pass
                raw = key_path.read_bytes()
                if len(raw) == 32:
                    return raw
            except Exception:
                pass

        # Generate fresh 256-bit CSPRNG key with OS urandom
        new_key = os.urandom(32)
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            mode = 0o600
            fd = os.open(str(key_path), flags, mode)
            with os.fdopen(fd, "wb") as f:
                f.write(new_key)
            if sys.platform != "win32":
                try:
                    os.chmod(key_path, 0o600)
                except Exception:
                    pass
            return new_key
        except Exception as e:
            raise KeyringUnavailableError(
                "Gagal menginisialisasi penyimpanan vault OS berizin aman (0o600). "
                "Penyimpanan kredensial dibatalkan secara fail-closed."
            ) from e

    def _shred_file(self, target: Path) -> None:
        """Overwrite file with zeros before unlinking to prevent disk recovery."""
        try:
            if target.exists():
                size = target.stat().st_size
                target.write_bytes(b"\x00" * max(size, 64))
                target.unlink(missing_ok=True)
        except Exception:
            try:
                target.unlink(missing_ok=True)
            except Exception:
                pass

    def _store_in_keyring(self, credential_ref: str, secret: str) -> bool:
        if self._force_keyring_failure or settings.testing:
            return False
        try:
            keyring.set_password(SERVICE_NAME, credential_ref, secret)
            return True
        except Exception:
            return False

    def _get_from_keyring(self, credential_ref: str) -> str | None:
        if self._force_keyring_failure or settings.testing:
            return None
        try:
            return keyring.get_password(SERVICE_NAME, credential_ref)
        except Exception:
            return None

    def _delete_from_keyring(self, credential_ref: str) -> bool:
        if self._force_keyring_failure or settings.testing:
            return False
        try:
            keyring.delete_password(SERVICE_NAME, credential_ref)
            return True
        except Exception:
            return False

    def _aesgcm_encrypt(self, plaintext: str, key: bytes) -> dict[str, str]:
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # Standard 96-bit nonce for AES-GCM
        ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return {
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ct).decode("ascii"),
        }

    def _aesgcm_decrypt(self, payload: dict[str, str], key: bytes) -> str | None:
        try:
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

    def _migrate_all_legacy_vaults_if_needed(self) -> None:
        """Migrate older vaults (HMAC-CTR and metadata-derived AES-GCM) into OS keyring/CSPRNG vault and shred legacy files."""
        if self._has_migrated_legacy:
            return
        self._has_migrated_legacy = True

        # 1. Migrate original HMAC-CTR vault if present
        if self.legacy_vault_file.exists():
            try:
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
                        stored = self._store_in_keyring(cred_ref, plain)
                        if not stored:
                            # Store in secure CSPRNG vault
                            k = self._get_or_create_os_vault_key()
                            entries = self._load_fallback_entries()
                            entries[cred_ref] = self._aesgcm_encrypt(plain, k)
                            self._save_fallback_entries(entries)
                        self._memory_cache[cred_ref] = plain

                self._shred_file(self.legacy_vault_file)
                if self.legacy_key_file.exists():
                    self._shred_file(self.legacy_key_file)
            except Exception:
                pass

        # 2. Migrate metadata-derived AES-GCM fallback vault to OS Keyring / CSPRNG key (P1.1)
        if (
            self.fallback_vault_file.exists()
            and not self.os_key_file.exists()
            and not self.dpapi_key_file.exists()
        ):
            try:
                legacy_meta_key = _derive_legacy_metadata_key()
                fallback_entries = self._load_fallback_entries()
                migrated_entries: dict[str, dict[str, str]] = {}
                secure_key: bytes | None = None

                for cred_ref, payload in list(fallback_entries.items()):
                    if isinstance(payload, dict) and "nonce" in payload and "ciphertext" in payload:
                        plain = self._aesgcm_decrypt(payload, legacy_meta_key)
                        if plain:
                            stored = self._store_in_keyring(cred_ref, plain)
                            if not stored:
                                if secure_key is None:
                                    secure_key = self._get_or_create_os_vault_key()
                                migrated_entries[cred_ref] = self._aesgcm_encrypt(plain, secure_key)
                            self._memory_cache[cred_ref] = plain

                if migrated_entries:
                    self._save_fallback_entries(migrated_entries)
                else:
                    self._shred_file(self.fallback_vault_file)
            except Exception:
                pass

        # 3. On Windows: migrate plaintext os_key_file to DPAPI protected key (P1-01)
        if sys.platform == "win32" and self.os_key_file.exists() and not self.dpapi_key_file.exists():
            try:
                raw_k = self.os_key_file.read_bytes()
                if len(raw_k) == 32:
                    protected = _dpapi_protect(raw_k)
                    if protected:
                        self.dpapi_key_file.write_bytes(protected)
                        self._shred_file(self.os_key_file)
            except Exception:
                pass

    def store_secret(self, provider: str, secret: str, existing_ref: str | None = None) -> dict[str, str]:
        """Store a secret in the OS keyring or secure CSPRNG vault fail-closed without metadata fallbacks (P1.1)."""
        cleaned = secret.strip()
        if not cleaned:
            raise ValueError("Secret tidak boleh kosong.")

        self._migrate_all_legacy_vaults_if_needed()
        cred_ref = existing_ref or f"cred_{provider}_{uuid.uuid4().hex[:10]}"

        # 1. Attempt OS Keyring storage first
        stored_in_os = self._store_in_keyring(cred_ref, cleaned)
        if stored_in_os:
            self._memory_cache[cred_ref] = cleaned
            return {
                "credential_ref": cred_ref,
                "provider": provider,
                "masked_preview": mask_secret(cleaned),
                "backend": "os_keyring",
                "updated_at": _now_iso(),
            }

        # 2. OS Keyring unavailable/denied: Use OS-permission-restricted CSPRNG vault key (0o600)
        try:
            key = self._get_or_create_os_vault_key()
            entries = self._load_fallback_entries()
            entries[cred_ref] = self._aesgcm_encrypt(cleaned, key)
            self._save_fallback_entries(entries)
            self._memory_cache[cred_ref] = cleaned
            return {
                "credential_ref": cred_ref,
                "provider": provider,
                "masked_preview": mask_secret(cleaned),
                "backend": "os_secure_file_vault",
                "updated_at": _now_iso(),
            }
        except KeyringUnavailableError:
            raise
        except Exception as e:
            raise KeyringUnavailableError(
                f"OS Keyring dan penyimpanan berkas berizin aman tidak tersedia untuk provider '{provider}'. "
                "Penyimpanan kredensial dibatalkan secara fail-closed."
            ) from e

    def retrieve_secret(self, credential_ref: str) -> str | None:
        """Retrieve a decrypted secret by its credential_ref."""
        if not credential_ref:
            return None
        if credential_ref in self._memory_cache:
            return self._memory_cache[credential_ref]

        self._migrate_all_legacy_vaults_if_needed()
        if credential_ref in self._memory_cache:
            return self._memory_cache[credential_ref]

        # 1. Check OS Keyring
        val = self._get_from_keyring(credential_ref)
        if val is not None:
            self._memory_cache[credential_ref] = val
            return val

        # 2. Check secure CSPRNG OS vault if key exists
        if self.fallback_vault_file.exists():
            try:
                key = self._get_or_create_os_vault_key()
                entries = self._load_fallback_entries()
                entry = entries.get(credential_ref)
                if entry:
                    decrypted = self._aesgcm_decrypt(entry, key)
                    if decrypted is not None:
                        self._memory_cache[credential_ref] = decrypted
                        return decrypted
            except Exception:
                pass

        # 3. Check legacy metadata fallback exclusively for reading un-migrated secrets
        if self.fallback_vault_file.exists():
            try:
                legacy_meta_key = _derive_legacy_metadata_key()
                entries = self._load_fallback_entries()
                entry = entries.get(credential_ref)
                if entry:
                    decrypted = self._aesgcm_decrypt(entry, legacy_meta_key)
                    if decrypted is not None:
                        self._memory_cache[credential_ref] = decrypted
                        return decrypted
            except Exception:
                pass

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
