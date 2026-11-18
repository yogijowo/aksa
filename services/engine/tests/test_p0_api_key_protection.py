"""Regression tests for P0-4: API key leakage prevention, header auth for Gemini, and response schema scrub."""

from __future__ import annotations

import re
from unittest.mock import patch
import pytest
from httpx import ASGITransport, AsyncClient, Response

from app.config import settings
from app.core.llm_router import UnifiedLLMRouter
from app.core.model_discovery import GeminiDiscoveryAdapter
from app.db.models import db_manager
from app.main import app


SECRET_PATTERN = re.compile(r"^(sk-[a-zA-Z0-9_\-]{8,}|AIza[a-zA-Z0-9_\-]{10,}|gsk_[a-zA-Z0-9_\-]{8,}|sk-ant-[a-zA-Z0-9_\-]{8,})")


def _assert_no_secrets_in_payload(obj: object, path: str = "root") -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            _assert_no_secrets_in_payload(v, f"{path}.{k}")
            if "key" in k.lower() and isinstance(v, str) and not k.endswith("_masked") and not k.endswith("_preview") and k != "env_key":
                assert not SECRET_PATTERN.search(v), f"Plaintext secret pattern found in field '{path}.{k}': {v[:6]}..."
                if len(v) > 16:
                    assert "••••" in v, f"Field '{path}.{k}' has unmasked secret length {len(v)}: {v[:6]}..."
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _assert_no_secrets_in_payload(item, f"{path}[{i}]")
    elif isinstance(obj, str):
        assert not SECRET_PATTERN.search(obj), f"Plaintext secret pattern found in string value at '{path}': {obj[:6]}..."


@pytest.mark.asyncio
async def test_p0_models_response_schema_never_exposes_plaintext_keys() -> None:
    """Verify that saving a key and querying /models/providers returns only masked preview and no raw secrets."""
    await db_manager.initialize()
    transport = ASGITransport(app=app)
    auth_headers = {"X-AKSA-Auth-Token": settings.auth_token}

    async with AsyncClient(transport=transport, base_url="http://test", headers=auth_headers) as client:
        # Save real-looking test keys
        await client.post("/api/v1/models/keys", json={"provider": "gemini", "api_key": "AIzaSyDTESTKEY1234567890abcdefghijklmn"})
        await client.post("/api/v1/models/keys", json={"provider": "openai", "api_key": "sk-proj-testkeyopenai1234567890abcdefgh"})
        await client.post("/api/v1/models/keys", json={"provider": "groq", "api_key": "gsk_testkeygroq1234567890abcdefghijklmn"})

        # Query providers
        resp = await client.get("/api/v1/models/providers")
        assert resp.status_code == 200
        data = resp.json()

        # Schema assertion: No field anywhere contains a raw secret
        _assert_no_secrets_in_payload(data)

        # Check discovered models endpoint
        resp_disc = await client.get("/api/v1/models/discovered")
        assert resp_disc.status_code == 200
        _assert_no_secrets_in_payload(resp_disc.json())


@pytest.mark.asyncio
async def test_p0_gemini_calls_pass_api_key_in_header_not_url() -> None:
    """Verify that Gemini REST discovery and completion pass x-goog-api-key header and have no ?key= in URL."""
    fake_key = "AIzaSyD_TEST_SAFE_KEY_12345"

    # 1. Gemini Discovery adapter
    adapter = GeminiDiscoveryAdapter()
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = Response(200, json={"models": [{"name": "models/gemini-2.5-flash", "inputTokenLimit": 1000000}]})
        models = await adapter.discover_models(fake_key)
        assert len(models) == 1

        mock_get.assert_called_once()
        called_url = str(mock_get.call_args[0][0])
        called_headers = mock_get.call_args[1].get("headers", {})

        assert "?key=" not in called_url, f"API key was leaked in URL query: {called_url}"
        assert called_headers.get("x-goog-api-key") == fake_key

    # 2. Gemini Completion in LLMRouter
    router = UnifiedLLMRouter(db=db_manager)
    await router.save_api_key("gemini", fake_key)

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "Jawaban aman"}], "role": "model"}}]},
        )
        res = await router.complete("gemini", "gemini-2.5-flash", [{"role": "user", "content": "halo"}])
        assert res["content"] == "Jawaban aman"

        mock_post.assert_called_once()
        called_post_url = str(mock_post.call_args[0][0])
        called_post_headers = mock_post.call_args[1].get("headers", {})

        assert "?key=" not in called_post_url, f"API key was leaked in URL query: {called_post_url}"
        assert called_post_headers.get("x-goog-api-key") == fake_key
