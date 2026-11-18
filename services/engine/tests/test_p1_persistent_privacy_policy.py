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


@pytest.mark.asyncio
async def test_confidential_data_requires_explicit_consent_even_in_cloud_by_choice():
    """Verify CONFIDENTIAL data requires explicit per-request consent even in CLOUD_BY_CHOICE mode (P1-05)."""
    gate = PrivacyPolicyGate()
    gate.provider_mode = ProviderMode.CLOUD_BY_CHOICE

    # 1. Without per-request consent -> blocked
    summary = gate.evaluate_disclosure(
        provider="anthropic",
        model_id="claude-3-7-sonnet",
        messages=[{"role": "user", "content": "Berikut rekening koran dan rahasia perusahaan"}],
        user_consent_granted=False,
    )
    assert summary.data_classification == DataClassification.CONFIDENTIAL
    assert summary.allowed is False
    assert summary.requires_explicit_consent is True
    assert "Persetujuan otomatis" not in summary.denial_reason
    assert "wajib mendapatkan persetujuan eksplisit per-request" in summary.denial_reason

    # 2. With per-request consent -> allowed
    summary_consented = gate.evaluate_disclosure(
        provider="anthropic",
        model_id="claude-3-7-sonnet",
        messages=[{"role": "user", "content": "Berikut rekening koran dan rahasia perusahaan"}],
        user_consent_granted=True,
    )
    assert summary_consented.allowed is True


@pytest.mark.asyncio
async def test_consent_scope_binding_rejects_mismatched_provider_or_model():
    """Verify consent scoped to provider A or model A does not allow provider B or model B (P1-05)."""
    gate = PrivacyPolicyGate()

    # Consent granted specifically for gemini / gemini-2.5-pro
    consent_scope = {"provider": "gemini", "model_id": "gemini-2.5-pro"}

    # Attempt to send to openai with gemini's consent
    mismatched = gate.evaluate_disclosure(
        provider="openai",
        model_id="gpt-4o",
        messages=[{"role": "user", "content": "Data rahasia perusahaan"}],
        user_consent_granted=True,
        consent_scope=consent_scope,
    )
    assert mismatched.allowed is False
    assert mismatched.requires_explicit_consent is True

    # Matching provider & model -> allowed
    matched = gate.evaluate_disclosure(
        provider="gemini",
        model_id="gemini-2.5-pro",
        messages=[{"role": "user", "content": "Data rahasia perusahaan"}],
        user_consent_granted=True,
        consent_scope=consent_scope,
    )
    assert matched.allowed is True


@pytest.mark.asyncio
async def test_regex_pii_detection_and_redacted_preview():
    """Verify regex-based secret/PII detection and redaction preview generation (P1-05)."""
    gate = PrivacyPolicyGate()

    raw_text = "Tolong periksa user dengan NIK 3302198877665544 dan key sk-abcdef12345678901234567890"
    summary = gate.evaluate_disclosure(
        provider="groq",
        model_id="llama-3.3-70b",
        messages=[{"role": "user", "content": raw_text}],
    )
    assert summary.data_classification == DataClassification.CONFIDENTIAL
    assert summary.redaction_applied is True
    assert "[REDACTED_NIK]" in summary.redacted_preview
    assert "[REDACTED_API_KEY]" in summary.redacted_preview
    assert "3302198877665544" not in summary.redacted_preview
    assert "sk-abcdef12345678901234567890" not in summary.redacted_preview


