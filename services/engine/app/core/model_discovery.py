"""Dynamic Multi-Provider Model Discovery, Capability Normalization, and Local/Cloud Routing."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import httpx
from pydantic import BaseModel, Field

from app.config import settings
from app.core.agent_directory import agent_directory_service
from app.core.privacy_gate import ProviderMode, privacy_policy_gate

logger = logging.getLogger("aksa.model_discovery")


class DiscoveredModel(BaseModel):
    """Normalized schema for models discovered live from official provider endpoints."""

    provider_id: str
    provider_model_id: str
    display_name: str
    description: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    context_window: int = 128000
    max_output_tokens: int = 4096
    input_modalities: list[str] = Field(default_factory=lambda: ["text"])
    output_modalities: list[str] = Field(default_factory=lambda: ["text"])
    lifecycle: str = "active"  # active, preview, deprecated, retired, unknown
    availability: str = "available"  # available, unavailable, requires_access, unknown
    pricing: dict[str, Any] = Field(
        default_factory=lambda: {
            "input_per_million": 0.0,
            "output_per_million": 0.0,
            "currency": "USD",
            "source": "catalog",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    discovered_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_verified_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BaseProviderAdapter(ABC):
    """Abstract adapter defining live discovery contract per provider."""

    provider_id: str
    name: str
    is_local: bool

    @abstractmethod
    async def discover_models(self, api_key: str | None = None) -> list[DiscoveredModel]:
        """Fetch model list from official provider API endpoint."""


class OpenAIDiscoveryAdapter(BaseProviderAdapter):
    provider_id = "openai"
    name = "OpenAI API"
    is_local = False

    async def discover_models(self, api_key: str | None = None) -> list[DiscoveredModel]:
        if not api_key:
            return []
        url = "https://api.openai.com/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        models: list[DiscoveredModel] = []
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    for item in data:
                        mid = item.get("id", "")
                        caps = ["text_input", "text_output", "tool_calling", "streaming", "json_schema"]
                        if "vision" in mid or "4o" in mid or "4.5" in mid:
                            caps.extend(["image_input", "computer_use"])
                        if "o1" in mid or "o3" in mid:
                            caps.append("reasoning")
                        if "embedding" in mid:
                            caps = ["embeddings"]

                        models.append(
                            DiscoveredModel(
                                provider_id="openai",
                                provider_model_id=mid,
                                display_name=f"OpenAI {mid}",
                                capabilities=caps,
                                context_window=128000 if "4o" in mid else 32000,
                                input_modalities=["text", "image"] if "image_input" in caps else ["text"],
                                output_modalities=["text"],
                                provider_metadata={"created": item.get("created"), "owned_by": item.get("owned_by")},
                            )
                        )
        except Exception as exc:
            logger.warning("OpenAI discovery failed: %s", exc)
        return models


class AnthropicDiscoveryAdapter(BaseProviderAdapter):
    provider_id = "anthropic"
    name = "Anthropic Claude API"
    is_local = False

    async def discover_models(self, api_key: str | None = None) -> list[DiscoveredModel]:
        if not api_key:
            return []
        url = "https://api.anthropic.com/v1/models"
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        models: list[DiscoveredModel] = []
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    for item in data:
                        mid = item.get("id", "")
                        display = item.get("display_name", mid)
                        caps = ["text_input", "image_input", "pdf_input", "text_output", "tool_calling", "streaming", "json_schema", "computer_use"]
                        if "3-7" in mid or "3.7" in mid:
                            caps.append("reasoning")

                        models.append(
                            DiscoveredModel(
                                provider_id="anthropic",
                                provider_model_id=mid,
                                display_name=display,
                                capabilities=caps,
                                context_window=200000,
                                max_output_tokens=8192,
                                input_modalities=["text", "image", "pdf"],
                                output_modalities=["text"],
                                provider_metadata=item,
                            )
                        )
        except Exception as exc:
            logger.warning("Anthropic discovery failed: %s", exc)
        return models


class GeminiDiscoveryAdapter(BaseProviderAdapter):
    provider_id = "gemini"
    name = "Google Gemini API"
    is_local = False

    async def discover_models(self, api_key: str | None = None) -> list[DiscoveredModel]:
        if not api_key:
            return []
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        headers = {"x-goog-api-key": api_key}
        models: list[DiscoveredModel] = []
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json().get("models", [])
                    for item in data:
                        raw_name = item.get("name", "")  # e.g. "models/gemini-2.5-flash"
                        mid = raw_name.replace("models/", "")
                        caps = ["text_input", "image_input", "audio_input", "video_input", "pdf_input", "text_output", "tool_calling", "streaming", "json_schema"]
                        if "pro" in mid or "2.5" in mid:
                            caps.append("reasoning")

                        ctx = item.get("inputTokenLimit", 1000000)
                        models.append(
                            DiscoveredModel(
                                provider_id="gemini",
                                provider_model_id=mid,
                                display_name=item.get("displayName", mid),
                                description=item.get("description"),
                                capabilities=caps,
                                context_window=ctx,
                                max_output_tokens=item.get("outputTokenLimit", 8192),
                                input_modalities=["text", "image", "audio", "video", "pdf"],
                                output_modalities=["text"],
                                provider_metadata=item,
                            )
                        )
        except Exception as exc:
            logger.warning("Gemini discovery failed: %s", exc)
        return models


class GenericOpenAICompatibleAdapter(BaseProviderAdapter):
    """Reusable adapter for Groq, DeepSeek, Mistral, xAI, and OpenRouter."""

    def __init__(self, provider_id: str, name: str, base_url: str, custom_models_path: str = "/models") -> None:
        self.provider_id = provider_id
        self.name = name
        self.is_local = False
        self.base_url = base_url.rstrip("/")
        self.models_path = custom_models_path

    async def discover_models(self, api_key: str | None = None) -> list[DiscoveredModel]:
        if not api_key:
            return []
        url = f"{self.base_url}{self.models_path}"
        headers = {"Authorization": f"Bearer {api_key}"}
        models: list[DiscoveredModel] = []
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    raw_data = resp.json()
                    items = raw_data.get("data") if isinstance(raw_data, dict) else []
                    if isinstance(items, list):
                        for item in items:
                            mid = item.get("id", "")
                            if not mid:
                                continue
                            caps = ["text_input", "text_output", "tool_calling", "streaming", "json_schema"]
                            if "r1" in mid or "reasoner" in mid or "deepseek-r1" in mid:
                                caps.append("reasoning")
                            if "vision" in mid:
                                caps.append("image_input")

                            models.append(
                                DiscoveredModel(
                                    provider_id=self.provider_id,
                                    provider_model_id=mid,
                                    display_name=f"{self.name}: {mid}",
                                    capabilities=caps,
                                    context_window=item.get("context_length", 128000),
                                    provider_metadata=item,
                                )
                            )
        except Exception as exc:
            logger.warning("%s discovery failed: %s", self.name, exc)
        return models


class OllamaDiscoveryAdapter(BaseProviderAdapter):
    provider_id = "ollama"
    name = "Ollama Local AI"
    is_local = True

    async def discover_models(self, api_key: str | None = None) -> list[DiscoveredModel]:
        url = f"{settings.ollama_base_url}/api/tags"
        models: list[DiscoveredModel] = []
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json().get("models", [])
                    for item in data:
                        name = item.get("name", "")
                        caps = ["text_input", "text_output", "streaming", "json_schema"]
                        if "coder" in name:
                            caps.append("tool_calling")
                        if "r1" in name or "reasoner" in name:
                            caps.append("reasoning")
                        if "llava" in name or "vision" in name:
                            caps.append("image_input")

                        models.append(
                            DiscoveredModel(
                                provider_id="ollama",
                                provider_model_id=f"ollama/{name}",
                                display_name=f"Ollama: {name}",
                                capabilities=caps,
                                context_window=item.get("details", {}).get("parameter_size_tokens", 32768),
                                lifecycle="active",
                                availability="available",
                                provider_metadata=item,
                            )
                        )
        except Exception:
            pass
        return models


class LMStudioDiscoveryAdapter(BaseProviderAdapter):
    provider_id = "lmstudio"
    name = "LM Studio Local"
    is_local = True

    async def discover_models(self, api_key: str | None = None) -> list[DiscoveredModel]:
        url = f"{settings.lmstudio_base_url}/models"
        models: list[DiscoveredModel] = []
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    for item in data:
                        mid = item.get("id", "")
                        models.append(
                            DiscoveredModel(
                                provider_id="lmstudio",
                                provider_model_id=f"lmstudio/{mid}",
                                display_name=f"LM Studio: {mid}",
                                capabilities=["text_input", "text_output", "streaming"],
                                lifecycle="active",
                                availability="available",
                                provider_metadata=item,
                            )
                        )
        except Exception:
            pass
        return models


class ModelDiscoveryService:
    """Orchestrates live provider adapters, caching, role-based recommendations, and privacy gates."""

    ROLE_CAPABILITY_REQUIREMENTS: dict[str, list[str]] = {
        "general": ["text_input", "text_output"],
        "coding": ["text_input", "text_output", "tool_calling"],
        "reasoning": ["text_input", "text_output", "reasoning"],
        "vision": ["image_input", "text_output"],
        "computer_use": ["image_input", "tool_calling"],
        "embeddings": ["embeddings"],
        "lightweight": ["text_input", "text_output"],
    }

    def __init__(self) -> None:
        self.adapters: dict[str, BaseProviderAdapter] = {
            "openai": OpenAIDiscoveryAdapter(),
            "anthropic": AnthropicDiscoveryAdapter(),
            "gemini": GeminiDiscoveryAdapter(),
            "xai": GenericOpenAICompatibleAdapter("xai", "xAI Grok", "https://api.x.ai/v1"),
            "mistral": GenericOpenAICompatibleAdapter("mistral", "Mistral AI", "https://api.mistral.ai/v1"),
            "deepseek": GenericOpenAICompatibleAdapter("deepseek", "DeepSeek", "https://api.deepseek.com"),
            "groq": GenericOpenAICompatibleAdapter("groq", "Groq Cloud", "https://api.groq.com/openai/v1"),
            "openrouter": GenericOpenAICompatibleAdapter("openrouter", "OpenRouter", "https://openrouter.ai/api/v1"),
            "ollama": OllamaDiscoveryAdapter(),
            "lmstudio": LMStudioDiscoveryAdapter(),
        }
        self._memory_cache: dict[str, list[DiscoveredModel]] = {}

    def _get_cache_file(self, provider_id: str) -> Path:
        cache_dir = agent_directory_service.root_dir / "system" / "provider-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / f"{provider_id}.json"

    def load_cached_models(self, provider_id: str) -> list[DiscoveredModel]:
        """Load discovered models from disk cache."""
        cache_file = self._get_cache_file(provider_id)
        if cache_file.exists():
            try:
                raw = json.loads(cache_file.read_text(encoding="utf-8"))
                return [DiscoveredModel(**item) for item in raw]
            except Exception as exc:
                logger.warning("Cache parse error for %s: %s", provider_id, exc)
        return []

    def save_cached_models(self, provider_id: str, models: list[DiscoveredModel]) -> None:
        """Persist discovered models to disk cache."""
        cache_file = self._get_cache_file(provider_id)
        payload = [m.model_dump() for m in models]
        cache_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self._memory_cache[provider_id] = models

    async def discover_provider(self, provider_id: str, api_key: str | None = None) -> list[DiscoveredModel]:
        """Discover models for a single provider; preserves cache on failure."""
        adapter = self.adapters.get(provider_id)
        if not adapter:
            return []

        # Check Privacy Gate: In LOCAL_ONLY mode, cloud discovery is strictly blocked
        if not adapter.is_local and privacy_policy_gate.provider_mode == ProviderMode.LOCAL_ONLY:
            return []

        try:
            discovered = await adapter.discover_models(api_key=api_key)
            if discovered:
                self.save_cached_models(provider_id, discovered)
                return discovered
        except Exception as exc:
            logger.error("Provider discovery network exception for %s: %s", provider_id, exc)

        # Resilient fallback: return existing cached models if live discovery failed
        return self._memory_cache.get(provider_id) or self.load_cached_models(provider_id)

    async def discover_all_active_providers(self, saved_api_keys: dict[str, str]) -> dict[str, list[DiscoveredModel]]:
        """Run discovery across all configured providers."""
        results: dict[str, list[DiscoveredModel]] = {}
        for pid, adapter in self.adapters.items():
            if adapter.is_local:
                models = await self.discover_provider(pid)
                results[pid] = models
            else:
                key = saved_api_keys.get(pid)
                if key:
                    models = await self.discover_provider(pid, api_key=key)
                    results[pid] = models
                else:
                    # Return cached models if any
                    results[pid] = self.load_cached_models(pid)
        return results

    def recommend_model_for_role(
        self, role: str, available_models: list[DiscoveredModel]
    ) -> DiscoveredModel | None:
        """Select optimal model matching role requirements and capability tags."""
        needed_caps = self.ROLE_CAPABILITY_REQUIREMENTS.get(role, ["text_input", "text_output"])
        for model in available_models:
            if all(cap in model.capabilities for cap in needed_caps):
                return model
        return available_models[0] if available_models else None


model_discovery_service = ModelDiscoveryService()
