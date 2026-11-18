"""Tests for P1-8: Persistent Telegram Whitelist & Single-Use Pairing with Lockout."""

from __future__ import annotations

import time
from pathlib import Path
import pytest

from app.db.models import DatabaseManager
from app.telegram.auth import TelegramAuthGuard


@pytest.mark.asyncio
async def test_p1_telegram_persistent_auth_and_restart(tmp_path: Path) -> None:
    """Verify that paired users persist across restarts in SQLite table telegram_allowed_users."""
    db = DatabaseManager(db_path=tmp_path / "test_tg.db")
    await db.initialize()

    guard1 = TelegramAuthGuard(db=db)
    code = guard1.pairing_code

    user_id = 987654321
    ok, reply = await guard1.verify_pairing_code(
        telegram_user_id=user_id,
        submitted_code=code,
        username="pns_kudus",
    )
    assert ok is True
    assert guard1.is_authorized(user_id) is True

    # Check persistence in SQLite
    persisted = await db.list_telegram_allowed_users()
    assert len(persisted) == 1
    assert persisted[0]["telegram_user_id"] == user_id
    assert persisted[0]["username"] == "pns_kudus"

    # Simulate restart by creating a new guard instance and loading from DB
    guard2 = TelegramAuthGuard(db=db)
    assert guard2.is_authorized(user_id) is False  # Before loading

    await guard2.load_from_db(db)
    assert guard2.is_authorized(user_id) is True  # Loaded from SQLite


@pytest.mark.asyncio
async def test_p1_telegram_pairing_code_single_use(tmp_path: Path) -> None:
    """Verify that pairing code is single-use and cannot be reused."""
    db = DatabaseManager(db_path=tmp_path / "test_tg.db")
    await db.initialize()

    guard = TelegramAuthGuard(db=db)
    code = guard.pairing_code

    user1 = 111111111
    user2 = 222222222

    # First user pairs successfully
    ok1, _ = await guard.verify_pairing_code(telegram_user_id=user1, submitted_code=code)
    assert ok1 is True
    assert guard.pairing_code == ""  # Burned

    # Second user tries to use the same code
    ok2, reply2 = await guard.verify_pairing_code(telegram_user_id=user2, submitted_code=code)
    assert ok2 is False
    assert "tidak aktif" in reply2 or "cocok" in reply2


@pytest.mark.asyncio
async def test_p1_telegram_pairing_code_5min_ttl(tmp_path: Path) -> None:
    """Verify that pairing code expires after 5 minutes (300 seconds)."""
    db = DatabaseManager(db_path=tmp_path / "test_tg.db")
    await db.initialize()

    guard = TelegramAuthGuard(db=db)
    code = guard.pairing_code

    # Age the code past 300 seconds
    guard._pairing_created_at = time.time() - 305

    ok, reply = await guard.verify_pairing_code(telegram_user_id=333333333, submitted_code=code)
    assert ok is False
    assert "kedaluwarsa" in reply


@pytest.mark.asyncio
async def test_p1_telegram_brute_force_lockout(tmp_path: Path) -> None:
    """Verify that 5 failed attempts trigger lockout, rejecting further attempts."""
    db = DatabaseManager(db_path=tmp_path / "test_tg.db")
    await db.initialize()

    guard = TelegramAuthGuard(db=db)

    # 5 wrong attempts
    for i in range(1, 5):
        ok, reply = await guard.verify_pairing_code(telegram_user_id=444444444, submitted_code="000000")
        assert ok is False
        assert f"percobaan {i}/5" in reply

    # 5th failed attempt locks the guard
    ok5, reply5 = await guard.verify_pairing_code(telegram_user_id=444444444, submitted_code="000000")
    assert ok5 is False
    assert "terkunci" in reply5

    # 6th attempt is rejected because guard is locked
    ok6, reply6 = await guard.verify_pairing_code(telegram_user_id=444444444, submitted_code="000000")
    assert ok6 is False
    assert "terkunci" in reply6
