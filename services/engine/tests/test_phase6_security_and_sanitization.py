"""Tests for Security Hardening, Credential Masking, WebSocket Session Isolation, and Dynamic PDF Extraction."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.api.ws import ConnectionManager
from app.core.llm_router import UnifiedLLMRouter
from app.core.orchestrator import _create_word_duplicate_from_pdf
from app.db.models import DatabaseManager
from app.tools.computer_use.gui_agent import computer_use_controller


@pytest.mark.asyncio
async def test_api_key_masking(tmp_path: Path) -> None:
    """Verify that list_providers_status masks API keys and never exposes plaintext secrets."""
    db_path = tmp_path / "test_keys.db"
    db = DatabaseManager(db_path=db_path)
    await db.initialize()

    router = UnifiedLLMRouter(db=db)
    # Save a test key
    await router.save_api_key("openai", "sk-proj-1234567890abcdefghijklmnop")

    providers = await router.list_providers_status()
    openai_prov = next((p for p in providers if p["id"] == "openai"), None)

    assert openai_prov is not None
    assert openai_prov["configured"] is True
    # Must NOT have raw plaintext "api_key" key exposed
    assert "api_key" not in openai_prov
    # Must have masked key
    assert "api_key_masked" in openai_prov
    assert openai_prov["api_key_masked"].startswith("sk-p")
    assert "••••••••" in openai_prov["api_key_masked"]
    assert "1234567890" not in openai_prov["api_key_masked"]


@pytest.mark.asyncio
async def test_websocket_session_isolation() -> None:
    """Verify that WebSocket broadcast_event isolates messages by session_id."""
    manager = ConnectionManager()

    # Client A subscribed to session_1
    ws_client_a = AsyncMock()
    ws_client_a.accept = AsyncMock()
    ws_client_a.send_text = AsyncMock()

    # Client B subscribed to session_2
    ws_client_b = AsyncMock()
    ws_client_b.accept = AsyncMock()
    ws_client_b.send_text = AsyncMock()

    # Client C global listener (no specific session subscribed)
    ws_client_c = AsyncMock()
    ws_client_c.accept = AsyncMock()
    ws_client_c.send_text = AsyncMock()

    await manager.connect(ws_client_a, session_id="session_1")
    await manager.connect(ws_client_b, session_id="session_2")
    await manager.connect(ws_client_c, session_id=None)

    # Broadcast event for session_1
    await manager.broadcast_event("test_step", {"detail": "secret_task_1"}, session_id="session_1")

    # Client A must receive it
    assert ws_client_a.send_text.call_count == 1
    call_msg_a = json.loads(ws_client_a.send_text.call_args[0][0])
    assert call_msg_a["event"] == "test_step"
    assert call_msg_a["session_id"] == "session_1"

    # Client B (session_2) must NOT receive session_1 event
    assert ws_client_b.send_text.call_count == 0

    # Client C (unscoped) must NOT receive private session_1 event (no cross-session leak)
    assert ws_client_c.send_text.call_count == 0

    # Global event (session_id=None) must be delivered to all
    await manager.broadcast_event("global_notice", {"msg": "update"}, session_id=None)
    assert ws_client_a.send_text.call_count == 2
    assert ws_client_b.send_text.call_count == 1
    assert ws_client_c.send_text.call_count == 1


@pytest.mark.asyncio
async def test_dynamic_pdf_duplicate(tmp_path: Path) -> None:
    """Verify that _create_word_duplicate_from_pdf generates a valid .docx dynamically from any PDF."""
    import reportlab.lib.pagesizes as ps
    from reportlab.pdfgen import canvas
    import docx

    sample_pdf = tmp_path / "Dokumen_Uji_Coba.pdf"
    c = canvas.Canvas(str(sample_pdf), pagesize=ps.A4)
    c.drawString(100, 750, "LAPORAN UJI COBA DINAMIS")
    c.drawString(100, 700, "Paragraf pengujian konversi tanpa template hardcoded.")
    c.save()

    target_docx = tmp_path / "Dokumen_Uji_Coba.docx"
    msg = _create_word_duplicate_from_pdf(sample_pdf, target_docx)

    assert target_docx.exists()
    assert target_docx.stat().st_size > 0
    assert "berhasil dibuat" in msg

    # Inspect generated docx content
    doc = docx.Document(str(target_docx))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "LAPORAN UJI COBA DINAMIS" in full_text
    assert "DPRD" not in full_text
    assert "Kudus" not in full_text


@pytest.mark.asyncio
async def test_computer_use_accurate_status(tmp_path: Path) -> None:
    """Verify that visual_screen_action returns honest status (simulated/unsupported) when driver is not present."""
    computer_use_controller.reset_emergency_stop()
    res = await computer_use_controller.visual_screen_action("click", x=500, y=500)

    # In environment without active GUI/pyautogui, status must report simulated
    assert res.data["status"] in ("executed", "simulated")
    if res.data["driver"] == "pyautogui":
        assert res.success is True
    else:
        assert res.success is False
        assert "simulated" in res.data["status"]
