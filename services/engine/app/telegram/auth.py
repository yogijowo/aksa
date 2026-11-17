"""Telegram Gateway Security: 6-Digit Pairing Code & Strict Numeric telegram_user_id Whitelist."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel


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
    """Enforces numeric Telegram User ID whitelist and 6-digit Desktop Pairing verification."""

    def __init__(self) -> None:
        self._pairing_code: str = f"{secrets.randbelow(900000) + 100000}"
        self._pairing_enabled: bool = True
        self._allowed_user_ids: set[int] = set()
        self._user_profiles: dict[int, dict[str, Any]] = {}
        self._audit_logs: list[TelegramAuditLog] = []

    @property
    def pairing_code(self) -> str:
        return self._pairing_code

    def regenerate_pairing_code(self) -> str:
        """Generate a fresh 6-digit pairing code and re-open pairing mode."""
        self._pairing_code = f"{secrets.randbelow(900000) + 100000}"
        self._pairing_enabled = True
        return self._pairing_code

    def is_authorized(self, telegram_user_id: int) -> bool:
        """Check if a numeric Telegram user ID is in the whitelist."""
        return telegram_user_id in self._allowed_user_ids

    def add_authorized_user(self, telegram_user_id: int, username: str = "pengguna_telegram") -> None:
        self._allowed_user_ids.add(telegram_user_id)
        self._user_profiles[telegram_user_id] = {
            "telegram_user_id": telegram_user_id,
            "username": username,
            "paired_at": _now_iso(),
        }

    def remove_authorized_user(self, telegram_user_id: int) -> bool:
        self._user_profiles.pop(telegram_user_id, None)
        if telegram_user_id in self._allowed_user_ids:
            self._allowed_user_ids.remove(telegram_user_id)
            return True
        return False

    def verify_pairing_code(
        self,
        telegram_user_id: int,
        submitted_code: str,
        username: str = "pengguna_telegram",
    ) -> tuple[bool, str]:
        """Verify `/pair <6-digit-code>` and lock whitelist to the user's numeric ID."""
        clean_submitted = submitted_code.replace("-", "").strip()
        clean_actual = self._pairing_code.replace("-", "").strip()

        if not self._pairing_enabled and telegram_user_id not in self._allowed_user_ids:
            self.record_log(
                telegram_user_id=telegram_user_id,
                username=username,
                event_type="blocked_intruder",
                detail_id="Percobaan pairing ditolak karena mode pairing sudah dikunci.",
            )
            return False, "Mode pairing sedang dikunci. Silakan buka kembali dari aplikasi Desktop AKSA."

        if clean_submitted != clean_actual:
            self.record_log(
                telegram_user_id=telegram_user_id,
                username=username,
                event_type="blocked_intruder",
                detail_id=f"Kode pairing salah dimasukkan: '{submitted_code}'.",
            )
            return False, "Kode pairing 6-digit tidak cocok. Periksa layar Desktop AKSA Anda."

        self.add_authorized_user(telegram_user_id, username=username)
        self._pairing_enabled = False
        self.record_log(
            telegram_user_id=telegram_user_id,
            username=username,
            event_type="paired",
            detail_id=f"Akun @{username} ({telegram_user_id}) berhasil dihubungkan & dikunci ke Whitelist.",
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

