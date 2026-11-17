"""Unified Multi-Model Router supporting Cloud APIs (LiteLLM) and Local AI (Ollama / LM Studio)."""

from __future__ import annotations

import json
import os
from typing import Any

import aiosqlite
import httpx

try:
    import litellm
except ImportError:  # pragma: no cover
    litellm = None  # type: ignore[assignment]

from app.config import settings
from app.core.token_optimizer import token_optimizer
from app.db.models import DatabaseManager, _now_iso

SUPPORTED_PROVIDERS: list[dict[str, Any]] = [
    {
        "id": "ollama",
        "name": "Ollama (AI Lokal Gratis)",
        "is_local": True,
        "base_url": "http://127.0.0.1:11434",
        "recommended_models": ["qwen2.5:7b", "qwen2.5-coder:7b", "llama3.2:3b", "gemma3:4b"],
    },
    {
        "id": "lmstudio",
        "name": "LM Studio (Server Lokal OpenAI)",
        "is_local": True,
        "base_url": "http://127.0.0.1:1234/v1",
        "recommended_models": ["gemma-3-12b-it", "qwen2.5-7b-instruct"],
    },
    {
        "id": "gemini",
        "name": "Google Gemini API",
        "is_local": False,
        "env_key": "GEMINI_API_KEY",
        "recommended_models": ["gemini-2.5-pro", "gemini-2.5-flash"],
    },
    {
        "id": "anthropic",
        "name": "Anthropic Claude API",
        "is_local": False,
        "env_key": "ANTHROPIC_API_KEY",
        "recommended_models": ["claude-3-7-sonnet-latest", "claude-3-5-haiku-latest"],
    },
    {
        "id": "deepseek",
        "name": "DeepSeek API",
        "is_local": False,
        "env_key": "DEEPSEEK_API_KEY",
        "recommended_models": ["deepseek-chat", "deepseek-reasoner"],
    },
    {
        "id": "openai",
        "name": "OpenAI API",
        "is_local": False,
        "env_key": "OPENAI_API_KEY",
        "recommended_models": ["gpt-4o", "gpt-4o-mini"],
    },
    {
        "id": "openrouter",
        "name": "OpenRouter API",
        "is_local": False,
        "env_key": "OPENROUTER_API_KEY",
        "recommended_models": ["anthropic/claude-3.7-sonnet", "google/gemini-2.5-pro"],
    },
    {
        "id": "groq",
        "name": "Groq Cloud (Inferensi Cepat)",
        "is_local": False,
        "env_key": "GROQ_API_KEY",
        "recommended_models": ["llama-3.3-70b-versatile"],
    },
]


class UnifiedLLMRouter:
    """Routes per-agent LLM requests to Cloud APIs (via LiteLLM) or Local Ollama / LM Studio."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    async def get_saved_api_keys(self) -> dict[str, str]:
        """Load stored API keys from SQLite app_settings."""
        async with aiosqlite.connect(self.db.db_path) as conn:
            cursor = await conn.execute(
                "SELECT value_json FROM app_settings WHERE key = 'provider_api_keys'"
            )
            row = await cursor.fetchone()
            if not row:
                return {}
            try:
                return json.loads(row[0])
            except Exception:
                return {}

    async def save_api_key(self, provider: str, api_key: str) -> dict[str, bool]:
        """Save a provider API key to SQLite and export it to the process environment."""
        keys = await self.get_saved_api_keys()
        if api_key.strip():
            keys[provider] = api_key.strip()
        else:
            keys.pop(provider, None)

        async with aiosqlite.connect(self.db.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO app_settings (key, value_json, updated_at)
                VALUES ('provider_api_keys', ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (json.dumps(keys), _now_iso()),
            )
            await conn.commit()

        for prov in SUPPORTED_PROVIDERS:
            if prov["id"] == provider and prov.get("env_key") and api_key.strip():
                os.environ[prov["env_key"]] = api_key.strip()

        return {p["id"]: bool(keys.get(p["id"])) for p in SUPPORTED_PROVIDERS if not p["is_local"]}

    async def discover_local_models(self) -> dict[str, Any]:
        """Auto-detect running Ollama and LM Studio instances and their installed models."""
        ollama_online = False
        ollama_models: list[str] = []
        lmstudio_online = False
        lmstudio_models: list[str] = []

        async with httpx.AsyncClient(timeout=1.5) as client:
            try:
                resp = await client.get(f"{settings.ollama_base_url}/api/tags")
                if resp.status_code == 200:
                    ollama_online = True
                    ollama_models = [m.get("name", "") for m in resp.json().get("models", [])]
            except Exception:
                pass

            try:
                resp_lm = await client.get(f"{settings.lmstudio_base_url}/models")
                if resp_lm.status_code == 200:
                    lmstudio_online = True
                    lmstudio_models = [m.get("id", "") for m in resp_lm.json().get("data", [])]
            except Exception:
                pass

        return {
            "ollama": {
                "online": ollama_online,
                "base_url": settings.ollama_base_url,
                "models": ollama_models,
            },
            "lmstudio": {
                "online": lmstudio_online,
                "base_url": settings.lmstudio_base_url,
                "models": lmstudio_models,
            },
        }

    async def list_providers_status(self) -> list[dict[str, Any]]:
        """Return all supported providers with key configuration status and local discovery."""
        saved_keys = await self.get_saved_api_keys()
        local_info = await self.discover_local_models()
        results: list[dict[str, Any]] = []

        for prov in SUPPORTED_PROVIDERS:
            pid = prov["id"]
            if pid == "ollama":
                results.append(
                    {
                        **prov,
                        "configured": True,
                        "online": local_info["ollama"]["online"],
                        "installed_models": local_info["ollama"]["models"],
                    }
                )
            elif pid == "lmstudio":
                results.append(
                    {
                        **prov,
                        "configured": True,
                        "online": local_info["lmstudio"]["online"],
                        "installed_models": local_info["lmstudio"]["models"],
                    }
                )
            else:
                env_key = prov.get("env_key", "")
                raw_k = saved_keys.get(pid) or os.environ.get(env_key) or ""
                has_key = bool(raw_k.strip())
                masked = ""
                if has_key:
                    k = raw_k.strip()
                    if len(k) > 8:
                        masked = f"{k[:4]}••••••••{k[-4:]}"
                    else:
                        masked = "••••••••"
                results.append(
                    {
                        **prov,
                        "configured": has_key,
                        "online": has_key,
                        "api_key_masked": masked,
                        "installed_models": prov["recommended_models"],
                    }
                )
        return results

    async def complete(
        self,
        provider: str,
        model_id: str,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 2048,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Execute an async completion via native REST APIs (Gemini, OpenAI, DeepSeek, Anthropic, Ollama)."""
        saved_keys = await self.get_saved_api_keys()
        api_key = saved_keys.get(provider) or os.environ.get(f"{provider.upper()}_API_KEY")

        # Smart provider fallback: if the requested provider has no key, route through an active key
        if not api_key and provider != "ollama":
            for active_prov in ("gemini", "deepseek", "openai", "anthropic", "groq", "openrouter"):
                candidate_key = saved_keys.get(active_prov) or os.environ.get(f"{active_prov.upper()}_API_KEY")
                if candidate_key:
                    provider = active_prov
                    api_key = candidate_key
                    if active_prov == "gemini":
                        model_id = "gemini-flash-latest"
                    elif active_prov == "deepseek":
                        model_id = "deepseek-chat"
                    elif active_prov == "openai":
                        model_id = "gpt-4o-mini"
                    break

        # 1. Google Gemini Native REST API
        if provider == "gemini" and api_key:
            clean_model = model_id.replace("gemini/", "").replace("google/", "")
            if clean_model in ("gemini-2.5-pro", "gemini-pro"):
                clean_model = "gemini-flash-latest"

            for candidate_model in [clean_model, "gemini-flash-latest", "gemini-2.5-flash-lite", "gemini-2.5-flash"]:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate_model}:generateContent?key={api_key}"
                system_text = "\n".join(m["content"] for m in messages if m["role"] == "system")
                user_contents = []
                for m in messages:
                    if m["role"] == "system":
                        continue
                    role = "user" if m["role"] == "user" else "model"
                    user_contents.append({"role": role, "parts": [{"text": m["content"]}]})
                if not user_contents:
                    user_contents.append({"role": "user", "parts": [{"text": "Halo"}]})

                if attachments:
                    for att in attachments:
                        user_contents[-1]["parts"].insert(
                            0,
                            {"inlineData": {"mimeType": att.get("mime_type", "application/pdf"), "data": att["data"]}}
                        )

                payload: dict[str, Any] = {
                    "contents": user_contents,
                    "generationConfig": {
                        "temperature": max(0.0, min(1.0, temperature)),
                        "maxOutputTokens": max_tokens,
                    },
                }
                if system_text:
                    payload["systemInstruction"] = {"parts": [{"text": system_text}]}

                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.post(url, json=payload)
                        if resp.status_code == 200:
                            data = resp.json()
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                content = "".join(p.get("text", "") for p in parts)
                                usage = data.get("usageMetadata", {})
                                return {
                                    "content": content,
                                    "input_tokens": usage.get("promptTokenCount", 150),
                                    "output_tokens": usage.get("candidatesTokenCount", 100),
                                    "simulated": False,
                                }
                except Exception:
                    continue

        # 2. OpenAI / DeepSeek / Groq / OpenRouter Compatible REST APIs
        if provider in ("openai", "deepseek", "groq", "openrouter") and api_key:
            base_urls = {
                "openai": "https://api.openai.com/v1",
                "deepseek": "https://api.deepseek.com",
                "groq": "https://api.groq.com/openai/v1",
                "openrouter": "https://openrouter.ai/api/v1",
            }
            base = base_urls.get(provider, "https://api.openai.com/v1")
            clean_model = model_id.replace(f"{provider}/", "")
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"{base}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={
                            "model": clean_model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        choice = data.get("choices", [{}])[0]
                        content = choice.get("message", {}).get("content", "")
                        usage = data.get("usage", {})
                        return {
                            "content": content,
                            "input_tokens": usage.get("prompt_tokens", 150),
                            "output_tokens": usage.get("completion_tokens", 100),
                            "simulated": False,
                        }
            except Exception:
                pass

        # 3. Anthropic Claude Native REST API
        if provider == "anthropic" and api_key:
            system_text = "\n".join(m["content"] for m in messages if m["role"] == "system")
            chat_msgs = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"]
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": model_id.replace("anthropic/", ""),
                            "system": system_text,
                            "messages": chat_msgs,
                            "max_tokens": max_tokens,
                            "temperature": temperature,
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        parts = data.get("content", [])
                        text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
                        usage = data.get("usage", {})
                        return {
                            "content": text,
                            "input_tokens": usage.get("input_tokens", 150),
                            "output_tokens": usage.get("output_tokens", 100),
                            "simulated": False,
                        }
            except Exception:
                pass

        # 4. Local Ollama API
        if provider == "ollama":
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        f"{settings.ollama_base_url}/api/chat",
                        json={
                            "model": model_id.replace("ollama/", ""),
                            "messages": messages,
                            "stream": False,
                            "options": {"temperature": temperature},
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        content = data.get("message", {}).get("content", "")
                        return {
                            "content": content,
                            "input_tokens": data.get(
                                "prompt_eval_count",
                                sum(token_optimizer.estimate_tokens(m["content"]) for m in messages),
                            ),
                            "output_tokens": data.get(
                                "eval_count", token_optimizer.estimate_tokens(content)
                            ),
                            "simulated": False,
                        }
            except Exception:
                pass

            # Fallback if Ollama daemon is offline or model missing: use active Cloud API key (e.g. Gemini)
            for active_prov in ("gemini", "deepseek", "openai", "anthropic"):
                candidate_key = saved_keys.get(active_prov) or os.environ.get(f"{active_prov.upper()}_API_KEY")
                if candidate_key:
                    fallback_model = (
                        "gemini-flash-latest"
                        if active_prov == "gemini"
                        else ("gpt-4o-mini" if active_prov == "openai" else "deepseek-chat")
                    )
                    return await self.complete(
                        provider=active_prov,
                        model_id=fallback_model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        attachments=attachments,
                    )

        # Fallback when no valid API key or offline daemon
        user_last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        simulated_reply = (
            f"Halo! Saya Asisten AKSA. Mohon pastikan Kunci API {provider.upper()} sudah disimpan di menu Pengaturan "
            f"atau server Ollama sudah berjalan di komputer Anda untuk mulai memproses instruksi: \"{user_last[:120]}\"."
        )
        return {
            "content": simulated_reply,
            "input_tokens": sum(token_optimizer.estimate_tokens(m["content"]) for m in messages),
            "output_tokens": token_optimizer.estimate_tokens(simulated_reply),
            "simulated": True,
        }

