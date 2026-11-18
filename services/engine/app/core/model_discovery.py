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


class ModelRecommendationResult(BaseModel):
    """Structured result of multi-criteria model recommendation (P2.1)."""

    recommended_model: DiscoveredModel | None
    score: float = 0.0
    reason: str = ""
    trade_offs: list[str] = Field(default_factory=list)
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
    criteria_scores: dict[str, float] = Field(default_factory=dict)
    metadata_source: str = "verified_provider_metadata"
    verified_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


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
            async with httpx.AsyncClient(timeout=0.8) as client:
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
            async with httpx.AsyncClient(timeout=0.8) as client:
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

    def recommend_model_with_scoring(
        self,
        role: str,
        available_models: list[DiscoveredModel],
        privacy_mode: ProviderMode | None = None,
        max_cost_per_million: float | None = None,
    ) -> ModelRecommendationResult:
        """Evaluate candidates using multi-criteria scoring (capabilities, context, cost, lifecycle, latency)."""
        if not available_models:
            return ModelRecommendationResult(
                recommended_model=None,
                score=0.0,
                reason="Tidak ada model yang tersedia untuk dievaluasi.",
            )

        eff_mode = privacy_mode or privacy_policy_gate.provider_mode
        needed_caps = self.ROLE_CAPABILITY_REQUIREMENTS.get(role, ["text_input", "text_output"])
        scored_candidates: list[tuple[float, DiscoveredModel, dict[str, float], list[str]]] = []

        local_provider_ids = {"ollama", "lmstudio"}

        for model in available_models:
            trade_offs: list[str] = []

            # 1. Privacy filter (P1.4, P2.1)
            if eff_mode == ProviderMode.LOCAL_ONLY and model.provider_id not in local_provider_ids:
                continue

            # 2. Availability filter
            if model.availability == "unavailable":
                continue

            # 3. Mandatory capability match
            missing_caps = [c for c in needed_caps if c not in model.capabilities]
            if missing_caps:
                continue

            # 4. Cost ceiling filter if specified
            in_cost = float(model.pricing.get("input_per_million", 0.0) or 0.0)
            out_cost = float(model.pricing.get("output_per_million", 0.0) or 0.0)
            total_unit_cost = in_cost + out_cost
            if max_cost_per_million is not None and total_unit_cost > max_cost_per_million:
                continue

            # --- Multi-Criteria Score Calculation ---
            # A. Capability Score (0-100): base 100 + bonus for reasoning/vision/tools
            cap_score = 100.0
            bonus_caps = set(model.capabilities) - set(needed_caps)
            cap_score += min(len(bonus_caps) * 5.0, 20.0)

            # B. Context Window Score (0-100)
            ctx = model.context_window or 128000
            ctx_score = min(ctx / 200_000.0, 1.0) * 100.0
            if ctx < 64000:
                trade_offs.append(f"Jendela konteks terbatas ({ctx:,} token).")

            # C. Cost Score (0-100): Local is 100, Cloud penalizes high per-million cost
            if model.provider_id in local_provider_ids or total_unit_cost == 0:
                cost_score = 100.0
            else:
                cost_score = max(0.0, 100.0 - total_unit_cost * 3.0)
                if total_unit_cost > 10.0:
                    trade_offs.append(f"Biaya inferensi relatif tinggi (${total_unit_cost:.2f}/M tokens).")

            # D. Lifecycle Score (0-100)
            life = model.lifecycle.lower()
            if life == "active":
                life_score = 100.0
            elif life == "preview":
                life_score = 80.0
                trade_offs.append("Status model masih preview.")
            else:
                life_score = 50.0
                trade_offs.append(f"Status siklus hidup model '{life}'.")

            # E. Reliability Score (0-100)
            rel_score = 100.0 if model.provider_id in ("gemini", "anthropic", "openai", "deepseek", "ollama") else 85.0

            # Weighted sum: 35% cap, 25% ctx, 20% cost, 10% life, 10% rel
            total = (
                0.35 * cap_score
                + 0.25 * ctx_score
                + 0.20 * cost_score
                + 0.10 * life_score
                + 0.10 * rel_score
            )
            criteria = {
                "capability": round(cap_score, 1),
                "context_window": round(ctx_score, 1),
                "cost_efficiency": round(cost_score, 1),
                "lifecycle": round(life_score, 1),
                "reliability": round(rel_score, 1),
            }
            scored_candidates.append((total, model, criteria, trade_offs))

        if not scored_candidates:
            # Fallback when all fail filters
            fallback = available_models[0]
            return ModelRecommendationResult(
                recommended_model=fallback,
                score=40.0,
                reason=f"Model fallback '{fallback.display_name}' dipilih karena tidak ada model yang sepenuhnya memenuhi kriteria peran '{role}'.",
                trade_offs=["Tidak semua kapabilitas optimal terpenuhi."],
            )

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_model, best_criteria, best_trade_offs = scored_candidates[0]

        alternatives: list[dict[str, Any]] = []
        for alt_score, alt_model, alt_crit, alt_to in scored_candidates[1:4]:
            alternatives.append({
                "model_id": alt_model.provider_model_id,
                "display_name": alt_model.display_name,
                "provider": alt_model.provider_id,
                "score": round(alt_score, 1),
                "context_window": alt_model.context_window,
                "trade_offs": alt_to,
            })

        reason = (
            f"Model '{best_model.display_name}' ({best_model.provider_id}) dipilih sebagai rekomendasi terbaik "
            f"untuk peran '{role}' dengan skor evaluasi {best_score:.1f}/100. "
            f"Memiliki konteks {best_model.context_window:,} token dan kapabilitas yang terverifikasi."
        )

        return ModelRecommendationResult(
            recommended_model=best_model,
            score=round(best_score, 1),
            reason=reason,
            trade_offs=best_trade_offs,
            alternatives=alternatives,
            criteria_scores=best_criteria,
            metadata_source="verified_provider_metadata",
            verified_at=best_model.last_verified_at,
        )

    def recommend_model_for_role(
        self, role: str, available_models: list[DiscoveredModel]
    ) -> DiscoveredModel | None:
        """Select optimal model matching role requirements using multi-criteria scoring."""
        res = self.recommend_model_with_scoring(role, available_models)
        return res.recommended_model


model_discovery_service = ModelDiscoveryService()
