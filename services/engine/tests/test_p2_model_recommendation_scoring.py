"""Tests for P2.1: Multi-Criteria Model Recommendation Scoring, Capability Filtering, and Privacy Guards."""

from __future__ import annotations

import pytest

from app.core.model_discovery import (
    DiscoveredModel,
    model_discovery_service,
)
from app.core.privacy_gate import ProviderMode


def _make_candidate(
    pid: str,
    mid: str,
    caps: list[str],
    ctx: int = 128000,
    in_cost: float = 1.0,
    out_cost: float = 2.0,
    avail: str = "available",
    life: str = "active",
) -> DiscoveredModel:
    return DiscoveredModel(
        provider_id=pid,
        provider_model_id=f"{pid}/{mid}",
        display_name=f"{pid.title()} {mid}",
        capabilities=caps,
        context_window=ctx,
        pricing={"input_per_million": in_cost, "output_per_million": out_cost},
        availability=avail,
        lifecycle=life,
    )


def test_multi_criteria_scoring_ranks_best_model():
    """Verify that a model with larger context, reasoning capability, and optimal cost scores higher."""
    models = [
        _make_candidate("openai", "gpt-3.5-legacy", ["text_input", "text_output"], ctx=16000, in_cost=0.5, out_cost=1.5),
        _make_candidate("anthropic", "claude-3-7-sonnet", ["text_input", "text_output", "reasoning", "tool_calling"], ctx=200000, in_cost=3.0, out_cost=15.0),
        _make_candidate("deepseek", "deepseek-chat", ["text_input", "text_output", "reasoning"], ctx=64000, in_cost=0.14, out_cost=0.28),
    ]

    res = model_discovery_service.recommend_model_with_scoring("reasoning", models)
    assert res.recommended_model is not None
    # Must be either Claude or DeepSeek, not legacy gpt-3.5
    assert res.recommended_model.provider_id in ("anthropic", "deepseek")
    assert res.score > 70.0
    assert len(res.alternatives) > 0
    assert "criteria_scores" in res.model_dump()
    assert res.metadata_source == "verified_provider_metadata"


def test_missing_mandatory_capability_filtered_out():
    """Verify that models lacking required capabilities (e.g. image_input for vision) are not recommended."""
    models = [
        _make_candidate("ollama", "qwen2.5-text-only", ["text_input", "text_output"]),
        _make_candidate("openai", "gpt-4o-vision", ["text_input", "text_output", "image_input", "tool_calling"]),
    ]

    res = model_discovery_service.recommend_model_with_scoring("vision", models)
    assert res.recommended_model is not None
    assert res.recommended_model.provider_model_id == "openai/gpt-4o-vision"


def test_cost_ceiling_filter():
    """Verify max_cost_per_million filters out expensive models."""
    models = [
        _make_candidate("openai", "o1-heavy", ["text_input", "text_output", "reasoning"], in_cost=15.0, out_cost=60.0),  # total 75.0
        _make_candidate("deepseek", "deepseek-r1", ["text_input", "text_output", "reasoning"], in_cost=0.55, out_cost=2.19),  # total 2.74
    ]

    res = model_discovery_service.recommend_model_with_scoring(
        "reasoning", models, max_cost_per_million=5.0
    )
    assert res.recommended_model is not None
    assert res.recommended_model.provider_model_id == "deepseek/deepseek-r1"


def test_privacy_restriction_filters_cloud_models():
    """Verify LOCAL_ONLY privacy mode excludes all cloud candidates."""
    models = [
        _make_candidate("openai", "gpt-4o", ["text_input", "text_output", "tool_calling"]),
        _make_candidate("gemini", "gemini-2.5-flash", ["text_input", "text_output", "tool_calling"]),
        _make_candidate("ollama", "qwen2.5-coder", ["text_input", "text_output", "tool_calling"], ctx=32000),
    ]

    res = model_discovery_service.recommend_model_with_scoring(
        "coding", models, privacy_mode=ProviderMode.LOCAL_ONLY
    )
    assert res.recommended_model is not None
    assert res.recommended_model.provider_id == "ollama"


def test_unavailable_models_excluded():
    """Verify models marked unavailable by provider status are excluded."""
    models = [
        _make_candidate("anthropic", "claude-3-outage", ["text_input", "text_output"], avail="unavailable"),
        _make_candidate("groq", "llama-3.3-70b", ["text_input", "text_output"], avail="available"),
    ]

    res = model_discovery_service.recommend_model_with_scoring("general", models)
    assert res.recommended_model is not None
    assert res.recommended_model.provider_id == "groq"

