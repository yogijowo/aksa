"""Tests for P1.4: Persistent Privacy Policy Gate, Fail-Closed Storage Errors, and Data Classification."""

from __future__ import annotations

import pytest

from app.core.privacy_gate import (
    DataClassification,
    PrivacyPolicyGate,
    ProviderMode,
)
from app.db.models import db_manager


@pytest.fixture(autouse=True)
async def init_db():
    await db_manager.initialize()


@pytest.mark.asyncio
async def test_privacy_policy_persists_across_instances():
    """Verify policy settings configured in one instance survive and reload in a new instance (P1.4)."""
    gate1 = PrivacyPolicyGate()
    await gate1.configure_and_persist(
        provider_mode=ProviderMode.HYBRID_WITH_CONSENT,
        default_classification=DataClassification.CONFIDENTIAL,
        allowed_providers=["gemini", "anthropic"],
        telemetry_opt_in=True,
        db=db_manager,
    )

    # Simulate restart by creating a completely new PrivacyPolicyGate instance
    gate2 = PrivacyPolicyGate()
    assert gate2.provider_mode == ProviderMode.CLOUD_BY_CHOICE  # Default before loading

    await gate2.ensure_loaded_from_db(db_manager)
    assert gate2.provider_mode == ProviderMode.HYBRID_WITH_CONSENT
    assert gate2.default_classification == DataClassification.CONFIDENTIAL
    assert gate2.allowed_enterprise_providers == {"gemini", "anthropic"}
    assert gate2.telemetry_opt_in is True


@pytest.mark.asyncio
async def test_storage_error_fails_closed():
    """Verify that if database storage fails, gate blocks external cloud requests fail-closed."""
    gate = PrivacyPolicyGate()
    gate._storage_error = True

    # Attempt cloud disclosure
    summary = gate.evaluate_disclosure(
        provider="gemini",
        model_id="gemini-2.5-flash",
        messages=[{"role": "user", "content": "Halo, tolong bantu analisa data"}],
    )
    assert summary.allowed is False
    assert "Storage Error" in summary.denial_reason
    assert "fail-closed" in summary.denial_reason


@pytest.mark.asyncio
async def test_restricted_data_blocked_from_cloud():
    """Verify data containing restricted markers is blocked from cloud providers."""
    gate = PrivacyPolicyGate()

    summary = gate.evaluate_disclosure(
        provider="openai",
        model_id="gpt-4o",
        messages=[{"role": "user", "content": "Ini adalah dokumen rahasia negara tentang pertahanan"}],
    )
    assert summary.data_classification == DataClassification.RESTRICTED
    assert summary.allowed is False
    assert "RESTRICTED" in summary.denial_reason


@pytest.mark.asyncio
async def test_local_only_mode_strictly_blocks_cloud():
    """Verify LOCAL_ONLY mode blocks cloud requests while allowing local providers."""
    gate = PrivacyPolicyGate()
    gate.provider_mode = ProviderMode.LOCAL_ONLY

    # Cloud request -> blocked
    cloud_summary = gate.evaluate_disclosure(
        provider="deepseek",
        model_id="deepseek-chat",
        messages=[{"role": "user", "content": "Analisa tabel"}],
    )
    assert cloud_summary.allowed is False
    assert "Local-Only" in cloud_summary.denial_reason

    # Local request -> allowed
    local_summary = gate.evaluate_disclosure(
        provider="ollama",
        model_id="qwen2.5:7b",
        messages=[{"role": "user", "content": "Analisa tabel"}],
    )
    assert local_summary.allowed is True
    assert "Pemrosesan lokal 100%" in local_summary.purpose

