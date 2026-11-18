"""Telegram Gateway Security: 6-Digit Pairing Code & Strict Numeric telegram_user_id Whitelist."""

from __future__ import annotations

import asyncio
import secrets
import time
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from app.db.models import DatabaseManager, db_manager


class TelegramAuditLog(BaseModel):
    """Security and activity log entry for the Telegram Gateway."""

    id: str
    timestamp: str
    telegram_user_id: int
    username: str
    event_type: str  # paired | authorized_command | blocked_intruder | voice_note | hitl_callback | file_delivered
    detail_id: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TelegramAuthGuard:
    """Enforces persistent numeric Telegram User ID whitelist and 5-minute single-use pairing code with brute-force lockout."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db: DatabaseManager | None = db
        self._pairing_code: str = f"{secrets.randbelow(900000) + 100000}"
        self._pairing_created_at: float = time.time()
        self._pairing_ttl_seconds: int = 300  # 5 minutes validity
        self._pairing_enabled: bool = True
        self._failed_pairing_attempts: int = 0
        self._max_attempts: int = 5
        self._is_locked: bool = False
        self._allowed_user_ids: set[int] = set()
        self._user_profiles: dict[int, dict[str, Any]] = {}
        self._audit_logs: list[TelegramAuditLog] = []

    def set_db(self, db: DatabaseManager) -> None:
        self.db = db

    async def load_from_db(self, db: DatabaseManager | None = None) -> None:
        """Load persistent authorized users from SQLite into memory on startup."""
        target_db = db or self.db or db_manager
        self.db = target_db
        try:
            records = await target_db.list_telegram_allowed_users()
            for r in records:
                uid = int(r["telegram_user_id"])
                self._allowed_user_ids.add(uid)
                self._user_profiles[uid] = {
                    "telegram_user_id": uid,
                    "username": r.get("username", "pengguna_telegram"),
                    "paired_at": r.get("paired_at", _now_iso()),
                }
        except Exception:
            pass

    @property
    def pairing_code(self) -> str:
        return self._pairing_code

    def regenerate_pairing_code(self) -> str:
        """Generate a fresh 6-digit pairing code and reset attempt counters."""
        self._pairing_code = f"{secrets.randbelow(900000) + 100000}"
        self._pairing_created_at = time.time()
        self._failed_pairing_attempts = 0
        self._is_locked = False
        self._pairing_enabled = True
        return self._pairing_code

    def is_authorized(self, telegram_user_id: int) -> bool:
        """Check if a numeric Telegram user ID is in the whitelist."""
        return telegram_user_id in self._allowed_user_ids

    async def add_authorized_user_async(self, telegram_user_id: int, username: str = "pengguna_telegram") -> None:
        self._allowed_user_ids.add(telegram_user_id)
        now = _now_iso()
        self._user_profiles[telegram_user_id] = {
            "telegram_user_id": telegram_user_id,
            "username": username,
            "paired_at": now,
        }
        target_db = self.db or db_manager
        try:
            await target_db.add_telegram_allowed_user(telegram_user_id, username)
        except Exception:
            pass

    def add_authorized_user(self, telegram_user_id: int, username: str = "pengguna_telegram") -> None:
        self._allowed_user_ids.add(telegram_user_id)
        now = _now_iso()
        self._user_profiles[telegram_user_id] = {
            "telegram_user_id": telegram_user_id,
            "username": username,
            "paired_at": now,
        }
        target_db = self.db or db_manager
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(target_db.add_telegram_allowed_user(telegram_user_id, username))
        except RuntimeError:
            pass

    async def remove_authorized_user_async(self, telegram_user_id: int) -> bool:
        self._user_profiles.pop(telegram_user_id, None)
        if telegram_user_id in self._allowed_user_ids:
            self._allowed_user_ids.remove(telegram_user_id)
            self.record_log(
                telegram_user_id=telegram_user_id,
                username="pengguna_telegram",
                event_type="unpaired",
                detail_id=f"Akses akun Telegram ({telegram_user_id}) telah dicabut dari Whitelist.",
            )
            target_db = self.db or db_manager
            try:
                await target_db.remove_telegram_allowed_user(telegram_user_id)
            except Exception:
                pass
            return True
        return False

    def remove_authorized_user(self, telegram_user_id: int) -> bool:
        self._user_profiles.pop(telegram_user_id, None)
        if telegram_user_id in self._allowed_user_ids:
            self._allowed_user_ids.remove(telegram_user_id)
            self.record_log(
                telegram_user_id=telegram_user_id,
                username="pengguna_telegram",
                event_type="unpaired",
                detail_id=f"Akses akun Telegram ({telegram_user_id}) telah dicabut dari Whitelist.",
            )
            target_db = self.db or db_manager
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(target_db.remove_telegram_allowed_user(telegram_user_id))
            except RuntimeError:
                pass
            return True
        return False

    async def verify_pairing_code(
        self,
        telegram_user_id: int,
        submitted_code: str,
        username: str = "pengguna_telegram",
    ) -> tuple[bool, str]:
        """Verify `/pair <6-digit-code>` with 5-minute TTL, single-use burn, and brute-force lockout."""
        clean_submitted = submitted_code.replace("-", "").strip()
        clean_actual = self._pairing_code.replace("-", "").strip()

        # 1. Check brute-force lockout
        if self._is_locked or self._failed_pairing_attempts >= self._max_attempts:
            self.record_log(
                telegram_user_id=telegram_user_id,
                username=username,
                event_type="blocked_intruder",
                detail_id="Percobaan pairing ditolak: mode pairing terkunci akibat 5 kali percobaan salah.",
            )
            return False, "Mode pairing sedang terkunci karena mencapai batas percobaan salah. Buat kode baru dari Desktop AKSA."

        # 2. Check 5-minute TTL
        elapsed = time.time() - self._pairing_created_at
        if elapsed > self._pairing_ttl_seconds:
            self._pairing_enabled = False
            self.record_log(
                telegram_user_id=telegram_user_id,
                username=username,
                event_type="blocked_intruder",
                detail_id=f"Percobaan pairing ditolak: kode telah kedaluwarsa ({round(elapsed)} detik).",
            )
            return False, "Kode pairing telah kedaluwarsa (berlaku maksimal 5 menit). Buat kode baru dari Desktop AKSA."

        # 3. Check if pairing mode is open
        if not self._pairing_enabled and telegram_user_id not in self._allowed_user_ids:
            self.record_log(
                telegram_user_id=telegram_user_id,
                username=username,
                event_type="blocked_intruder",
                detail_id="Percobaan pairing ditolak karena mode pairing sedang tidak aktif.",
            )
            return False, "Mode pairing sedang tidak aktif. Silakan buka kembali dari aplikasi Desktop AKSA."

        # 4. Verify code match
        if clean_submitted != clean_actual:
            self._failed_pairing_attempts += 1
            if self._failed_pairing_attempts >= self._max_attempts:
                self._is_locked = True
                self._pairing_enabled = False
                self.record_log(
                    telegram_user_id=telegram_user_id,
                    username=username,
                    event_type="blocked_intruder",
                    detail_id="Mode pairing otomatis DIKUNCI setelah 5 kali salah memasukkan kode.",
                )
                return False, "Kode pairing salah. Mode pairing kini terkunci demi keamanan. Buat kode baru dari Desktop AKSA."

            self.record_log(
                telegram_user_id=telegram_user_id,
                username=username,
                event_type="blocked_intruder",
                detail_id=f"Kode pairing salah dimasukkan (percobaan {self._failed_pairing_attempts}/{self._max_attempts}): '{submitted_code}'.",
            )
            return False, f"Kode pairing 6-digit tidak cocok (percobaan {self._failed_pairing_attempts}/{self._max_attempts}). Periksa layar Desktop AKSA Anda."

        # 5. Success: Burn code (single-use) and add to persistent whitelist
        await self.add_authorized_user_async(telegram_user_id, username=username)
        self._pairing_enabled = False
        self._pairing_code = ""  # Single-use: cleared immediately
        self._failed_pairing_attempts = 0
        self.record_log(
            telegram_user_id=telegram_user_id,
            username=username,
            event_type="paired",
            detail_id=f"Akun @{username} ({telegram_user_id}) berhasil dihubungkan & disimpan ke Whitelist SQLite.",
        )
        return (
            True,
            f"✅ Perangkat berhasil dihubungkan! Akun Telegram Anda (`{telegram_user_id}`) kini terdaftar sebagai pengendali resmi AKSA PC.",
        )

    def record_log(
        self,
        telegram_user_id: int,
        username: str,
        event_type: str,
        detail_id: str,
    ) -> TelegramAuditLog:
        entry = TelegramAuditLog(
            id=f"tglog_{len(self._audit_logs) + 1}_{secrets.token_hex(3)}",
            timestamp=_now_iso(),
            telegram_user_id=telegram_user_id,
            username=username,
            event_type=event_type,
            detail_id=detail_id,
        )
        self._audit_logs.insert(0, entry)
        del self._audit_logs[100:]
        return entry

    def list_authorized_users(self) -> list[dict[str, Any]]:
        return list(self._user_profiles.values())

    def list_logs(self) -> list[dict[str, Any]]:
        return [item.model_dump() for item in self._audit_logs]


telegram_auth_guard = TelegramAuthGuard()

