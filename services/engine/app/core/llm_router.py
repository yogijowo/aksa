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
from app.core.credential_vault import CredentialVault, mask_secret
from app.core.privacy_gate import DataClassification, ProviderMode, privacy_policy_gate
from app.core.token_optimizer import token_optimizer
from app.db.models import DatabaseManager, _now_iso

SUPPORTED_PROVIDERS: list[dict[str, Any]] = [
    {
        "id": "gemini",
        "name": "Google Gemini API",
        "is_local": False,
        "env_key": "GEMINI_API_KEY",
        "recommended_models": [
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ],
    },
    {
        "id": "anthropic",
        "name": "Anthropic Claude API",
        "is_local": False,
        "env_key": "ANTHROPIC_API_KEY",
        "recommended_models": [
            "claude-3-7-sonnet-latest",
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
            "claude-3-opus-latest",
        ],
    },
    {
        "id": "openai",
        "name": "OpenAI API",
        "is_local": False,
        "env_key": "OPENAI_API_KEY",
        "recommended_models": [
            "gpt-4.5-preview",
            "o3-mini",
            "o1",
            "gpt-4o",
            "gpt-4o-mini",
        ],
    },
    {
        "id": "deepseek",
        "name": "DeepSeek API",
        "is_local": False,
        "env_key": "DEEPSEEK_API_KEY",
        "recommended_models": [
            "deepseek-chat",
            "deepseek-reasoner",
        ],
    },
    {
        "id": "groq",
        "name": "Groq Cloud (Inferensi Cepat)",
        "is_local": False,
        "env_key": "GROQ_API_KEY",
        "recommended_models": [
            "llama-3.3-70b-versatile",
            "deepseek-r1-distill-llama-70b",
            "llama-3.1-8b-instant",
            "qwen-2.5-32b",
            "mixtral-8x7b-32768",
        ],
    },
    {
        "id": "openrouter",
        "name": "OpenRouter API",
        "is_local": False,
        "env_key": "OPENROUTER_API_KEY",
        "recommended_models": [
            "anthropic/claude-3.7-sonnet",
            "anthropic/claude-3.5-sonnet",
            "google/gemini-2.5-pro",
            "google/gemini-2.5-flash",
            "deepseek/deepseek-r1",
            "deepseek/deepseek-chat",
            "openai/gpt-4.5-preview",
            "openai/gpt-4o",
            "meta-llama/llama-3.3-70b-instruct",
            "openrouter/auto",
        ],
    },
    {
        "id": "ollama",
        "name": "Ollama (AI Lokal Gratis)",
        "is_local": True,
        "base_url": "http://127.0.0.1:11434",
        "recommended_models": [
            "qwen2.5:7b",
            "qwen2.5-coder:7b",
            "llama3.3:70b",
            "llama3.2:3b",
            "deepseek-r1:8b",
            "phi4:14b",
            "mistral:7b",
            "gemma2:9b",
        ],
    },
    {
        "id": "lmstudio",
        "name": "LM Studio (Server Lokal OpenAI)",
        "is_local": True,
        "base_url": "http://127.0.0.1:1234/v1",
        "recommended_models": [
            "qwen2.5-7b-instruct",
            "deepseek-r1-distill-qwen-7b",
            "llama-3.3-70b-instruct",
            "gemma-2-9b-it",
            "phi-4",
        ],
    },
]


class UnifiedLLMRouter:
    """Routes per-agent LLM requests to Cloud APIs or Local Ollama / LM Studio with strict privacy gates."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db
        self.vault = CredentialVault(vault_dir=self.db.db_path.parent)

    async def migrate_legacy_plaintext_keys(self) -> int:
        """One-time transactional migration of plaintext API keys from app_settings to OS Credential Vault."""
        migrated_count = 0
        async with aiosqlite.connect(self.db.db_path) as conn:
            cursor = await conn.execute(
                "SELECT value_json FROM app_settings WHERE key = 'provider_api_keys'"
            )
            row = await cursor.fetchone()
            if not row or not row[0]:
                return 0
            try:
                legacy_keys = json.loads(row[0])
            except Exception:
                return 0

            if not isinstance(legacy_keys, dict):
                return 0

            all_verified = True
            for prov, raw_secret in legacy_keys.items():
                if not isinstance(raw_secret, str) or not raw_secret.strip():
                    continue
                stored = self.vault.store_secret(prov, raw_secret.strip())
                # Verify secret can be retrieved from vault before scrubbing plaintext
                verified = self.vault.retrieve_secret(stored["credential_ref"])
                if verified != raw_secret.strip():
                    all_verified = False
                    break
                await self.db.upsert_credential_metadata(
                    provider=prov,
                    credential_ref=stored["credential_ref"],
                    masked_preview=stored["masked_preview"],
                    backend=stored["backend"],
                )
                migrated_count += 1

            if all_verified:
                await conn.execute("DELETE FROM app_settings WHERE key = 'provider_api_keys'")
                await conn.commit()

        return migrated_count

    async def get_saved_api_keys(self) -> dict[str, str]:
        """Resolve stored API keys from OS Credential Vault via SQLite credential_ref metadata."""
        await self.migrate_legacy_plaintext_keys()
        meta_rows = await self.db.list_credentials_metadata()
        resolved: dict[str, str] = {}
        for row in meta_rows:
            prov = row.get("provider")
            cred_ref = row.get("credential_ref")
            if prov and cred_ref:
                secret = self.vault.retrieve_secret(cred_ref)
                if secret:
                    resolved[prov] = secret
        return resolved

    async def save_api_key(self, provider: str, api_key: str) -> dict[str, bool]:
        """Store a provider API key in OS Credential Vault and save only its reference in SQLite."""
        await self.migrate_legacy_plaintext_keys()
        existing_meta = await self.db.get_credential_metadata(provider)
        existing_ref = existing_meta.get("credential_ref") if existing_meta else None

        if api_key.strip():
            stored = self.vault.store_secret(provider, api_key.strip(), existing_ref=existing_ref)
            await self.db.upsert_credential_metadata(
                provider=provider,
                credential_ref=stored["credential_ref"],
                masked_preview=stored["masked_preview"],
                backend=stored["backend"],
            )
        else:
            if existing_ref:
                self.vault.delete_secret(existing_ref)
            await self.db.delete_credential_metadata(provider)

        keys = await self.get_saved_api_keys()
        return {p["id"]: bool(keys.get(p["id"])) for p in SUPPORTED_PROVIDERS if not p["is_local"]}

    async def revoke_api_key(self, provider: str) -> bool:
        """Revoke and delete a provider API key from OS Credential Vault and SQLite metadata."""
        existing_meta = await self.db.get_credential_metadata(provider)
        if existing_meta and existing_meta.get("credential_ref"):
            self.vault.delete_secret(existing_meta["credential_ref"])
        return await self.db.delete_credential_metadata(provider)

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
        """Return all supported providers with vault reference status and local discovery (no plaintext keys)."""
        await self.migrate_legacy_plaintext_keys()
        meta_list = await self.db.list_credentials_metadata()
        meta_by_prov = {m["provider"]: m for m in meta_list}
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
                meta = meta_by_prov.get(pid)
                env_key = prov.get("env_key", "")
                env_val = os.environ.get(env_key, "").strip() if env_key else ""
                has_key = bool(meta or env_val)
                masked = (
                    meta["masked_preview"]
                    if meta and meta.get("masked_preview")
                    else (mask_secret(env_val) if env_val else "")
                )
                results.append(
                    {
                        **prov,
                        "configured": has_key,
                        "online": has_key,
                        "credential_ref": meta["credential_ref"] if meta else None,
                        "api_key_masked": masked,
                        "installed_models": prov["recommended_models"],
                    }
                )
        return results

    async def complete(
        self,
        provider: str,
        model_id: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 2048,
        attachments: list[dict[str, Any]] | None = None,
        data_classification: str | DataClassification | None = None,
        user_consent_granted: bool = False,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Execute an async completion enforcing PrivacyPolicyGate, tool calling, and zero local-to-cloud fallback."""
        prov = provider.lower().strip()

        # 0. Evaluate DataDisclosureGate & ProviderMode BEFORE any network activity
        disclosure = privacy_policy_gate.evaluate_disclosure(
            provider=prov,
            model_id=model_id,
            messages=messages,
            attachments=attachments,
            explicit_classification=data_classification,
            user_consent_granted=user_consent_granted,
        )
        if not disclosure.allowed:
            return {
                "content": f"[Diblokir oleh Kebijakan Privasi AKSA] {disclosure.denial_reason}",
                "tool_calls": [],
                "input_tokens": sum(token_optimizer.estimate_tokens(str(m.get("content") or "")) for m in messages),
                "output_tokens": 24,
                "simulated": True,
                "blocked_by_privacy_gate": True,
                "cloud_called": False,
                "disclosure": disclosure.model_dump(),
            }

        # 1. Local Providers (Ollama / LM Studio) — NEVER fall back to cloud!
        if prov == "ollama":
            try:
                body: dict[str, Any] = {
                    "model": model_id.replace("ollama/", ""),
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temperature},
                }
                if tools:
                    body["tools"] = tools
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        f"{settings.ollama_base_url}/api/chat",
                        json=body,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        msg = data.get("message", {})
                        content = msg.get("content", "")
                        raw_tool_calls = msg.get("tool_calls", [])
                        tool_calls = []
                        for tc in raw_tool_calls:
                            fn = tc.get("function", {})
                            tool_calls.append({
                                "id": tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                                "type": "function",
                                "function": {
                                    "name": fn.get("name"),
                                    "arguments": json.dumps(fn.get("arguments", {})) if isinstance(fn.get("arguments"), dict) else str(fn.get("arguments", "{}")),
                                },
                            })
                        return {
                            "content": content,
                            "tool_calls": tool_calls,
                            "input_tokens": data.get(
                                "prompt_eval_count",
                                sum(token_optimizer.estimate_tokens(str(m.get("content") or "")) for m in messages),
                            ),
                            "output_tokens": data.get(
                                "eval_count", token_optimizer.estimate_tokens(content)
                            ),
                            "simulated": False,
                            "cloud_called": False,
                            "provider_used": "ollama",
                        }
            except Exception:
                pass

            user_last = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
            offline_msg = (
                f"Server AI Lokal (Ollama) untuk model '{model_id}' saat ini tidak dapat dijangkau di {settings.ollama_base_url}. "
                f"Sesuai kebijakan keamanan AKSA (Tanpa Fallback ke Cloud), data Anda tetap tersimpan 100% lokal dan tidak dikirim ke penyedia cloud mana pun. "
                f"Konteks tugas lokal: \"{str(user_last)[:120]}\"."
            )
            return {
                "content": offline_msg,
                "tool_calls": [],
                "input_tokens": sum(token_optimizer.estimate_tokens(str(m.get("content") or "")) for m in messages),
                "output_tokens": token_optimizer.estimate_tokens(offline_msg),
                "simulated": True,
                "cloud_called": False,
                "provider_used": "ollama",
            }

        if prov == "lmstudio":
            try:
                body_lms: dict[str, Any] = {
                    "model": model_id.replace("lmstudio/", ""),
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if tools:
                    body_lms["tools"] = tools
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        f"{settings.lmstudio_base_url}/chat/completions",
                        json=body_lms,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        choice = data.get("choices", [{}])[0]
                        msg = choice.get("message", {})
                        content = msg.get("content", "")
                        tool_calls = msg.get("tool_calls", [])
                        usage = data.get("usage", {})
                        return {
                            "content": content,
                            "tool_calls": tool_calls,
                            "input_tokens": usage.get("prompt_tokens", 150),
                            "output_tokens": usage.get("completion_tokens", 100),
                            "simulated": False,
                            "cloud_called": False,
                            "provider_used": "lmstudio",
                        }
            except Exception:
                pass

            user_last = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
            offline_msg = (
                f"Server AI Lokal (LM Studio) untuk model '{model_id}' saat ini tidak aktif di {settings.lmstudio_base_url}. "
                f"Sesuai kebijakan keamanan AKSA (Tanpa Fallback ke Cloud), tidak ada data yang dikirim keluar perangkat. "
                f"Konteks tugas lokal: \"{str(user_last)[:120]}\"."
            )
            return {
                "content": offline_msg,
                "tool_calls": [],
                "input_tokens": sum(token_optimizer.estimate_tokens(str(m.get("content") or "")) for m in messages),
                "output_tokens": token_optimizer.estimate_tokens(offline_msg),
                "simulated": True,
                "cloud_called": False,
                "provider_used": "lmstudio",
            }

        # 2. Cloud Providers — strictly use ONLY the requested provider's key (no silent cross-provider routing)
        saved_keys = await self.get_saved_api_keys()
        api_key = saved_keys.get(prov) or os.environ.get(f"{prov.upper()}_API_KEY")

        # 2a. Google Gemini Native REST API
        if prov == "gemini" and api_key:
            clean_model = model_id.replace("gemini/", "").replace("google/", "")
            if clean_model in ("gemini-2.5-pro", "gemini-pro"):
                clean_model = "gemini-flash-latest"

            for candidate_model in [clean_model, "gemini-flash-latest", "gemini-2.5-flash-lite", "gemini-2.5-flash"]:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate_model}:generateContent"
                headers = {
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                }
                system_text = "\n".join(str(m.get("content") or "") for m in messages if m.get("role") == "system")
                user_contents = []
                for m in messages:
                    if m.get("role") == "system":
                        continue
                    role = "user" if m.get("role") in ("user", "tool") else "model"
                    user_contents.append({"role": role, "parts": [{"text": str(m.get("content") or "")}]})
                if not user_contents:
                    user_contents.append({"role": "user", "parts": [{"text": "Halo"}]})

                if attachments and user_consent_granted:
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

                if tools:
                    function_declarations = []
                    for t in tools:
                        fn = t.get("function", t)
                        decl: dict[str, Any] = {
                            "name": fn["name"],
                            "description": fn.get("description", ""),
                        }
                        if fn.get("parameters"):
                            decl["parameters"] = fn["parameters"]
                        function_declarations.append(decl)
                    payload["tools"] = [{"functionDeclarations": function_declarations}]

                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.post(url, json=payload, headers=headers)
                        if resp.status_code == 200:
                            data = resp.json()
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                content_parts = []
                                tool_calls = []
                                for p in parts:
                                    if "text" in p:
                                        content_parts.append(p["text"])
                                    elif "functionCall" in p:
                                        fc = p["functionCall"]
                                        tool_calls.append({
                                            "id": f"call_{uuid.uuid4().hex[:8]}",
                                            "type": "function",
                                            "function": {
                                                "name": fc.get("name"),
                                                "arguments": json.dumps(fc.get("args", {})),
                                            },
                                        })
                                content = "".join(content_parts)
                                usage = data.get("usageMetadata", {})
                                return {
                                    "content": content,
                                    "tool_calls": tool_calls,
                                    "input_tokens": usage.get("promptTokenCount", 150),
                                    "output_tokens": usage.get("candidatesTokenCount", 100),
                                    "simulated": False,
                                    "cloud_called": True,
                                    "provider_used": "gemini",
                                }
                except Exception:
                    continue

        # 2b. OpenAI / DeepSeek / Groq / OpenRouter Compatible REST APIs
        if prov in ("openai", "deepseek", "groq", "openrouter") and api_key:
            base_urls = {
                "openai": "https://api.openai.com/v1",
                "deepseek": "https://api.deepseek.com",
                "groq": "https://api.groq.com/openai/v1",
                "openrouter": "https://openrouter.ai/api/v1",
            }
            base = base_urls.get(prov, "https://api.openai.com/v1")
            clean_model = model_id.replace(f"{prov}/", "")
            req_body: dict[str, Any] = {
                "model": clean_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if tools:
                req_body["tools"] = tools
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"{base}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json=req_body,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        choice = data.get("choices", [{}])[0]
                        msg = choice.get("message", {})
                        content = msg.get("content", "") or ""
                        tool_calls = msg.get("tool_calls", [])
                        usage = data.get("usage", {})
                        return {
                            "content": content,
                            "tool_calls": tool_calls,
                            "input_tokens": usage.get("prompt_tokens", 150),
                            "output_tokens": usage.get("completion_tokens", 100),
                            "simulated": False,
                            "cloud_called": True,
                            "provider_used": prov,
                        }
            except Exception:
                pass

        # 2c. Anthropic Claude Native REST API
        if prov == "anthropic" and api_key:
            system_text = "\n".join(str(m.get("content") or "") for m in messages if m.get("role") == "system")
            chat_msgs = [{"role": m.get("role", "user"), "content": str(m.get("content") or "")} for m in messages if m.get("role") != "system"]
            req_body_anthropic: dict[str, Any] = {
                "model": model_id.replace("anthropic/", ""),
                "system": system_text,
                "messages": chat_msgs,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if tools:
                anthropic_tools = []
                for t in tools:
                    fn = t.get("function", t)
                    anthropic_tools.append({
                        "name": fn["name"],
                        "description": fn.get("description", ""),
                        "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                    })
                req_body_anthropic["tools"] = anthropic_tools
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json=req_body_anthropic,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        parts = data.get("content", [])
                        content_parts = []
                        tool_calls = []
                        for p in parts:
                            if p.get("type") == "text":
                                content_parts.append(p.get("text", ""))
                            elif p.get("type") == "tool_use":
                                tool_calls.append({
                                    "id": p.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                                    "type": "function",
                                    "function": {
                                        "name": p.get("name"),
                                        "arguments": json.dumps(p.get("input", {})),
                                    },
                                })
                        content = "".join(content_parts)
                        usage = data.get("usage", {})
                        return {
                            "content": content,
                            "tool_calls": tool_calls,
                            "input_tokens": usage.get("input_tokens", 150),
                            "output_tokens": usage.get("output_tokens", 100),
                            "simulated": False,
                            "cloud_called": True,
                            "provider_used": "anthropic",
                        }
            except Exception:
                pass

        # Fallback when no valid API key for the requested provider
        user_last = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
        simulated_reply = (
            f"Halo! Saya Asisten AKSA. Mohon pastikan Kunci API {prov.upper()} sudah disimpan di menu Pengaturan "
            f"atau gunakan model lokal untuk memproses instruksi: \"{str(user_last)[:120]}\"."
        )
        return {
            "content": simulated_reply,
            "tool_calls": [],
            "input_tokens": sum(token_optimizer.estimate_tokens(str(m.get("content") or "")) for m in messages),
            "output_tokens": token_optimizer.estimate_tokens(simulated_reply),
            "simulated": True,
            "cloud_called": False,
            "provider_used": prov,
        }

